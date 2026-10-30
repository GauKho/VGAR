"""Opt-in diff normalization (patch_mode='normalized'): relocate hunks by exact unique context.

Only header line numbers/offsets and a missing leading space on blank context lines are forgiven.
Path, protection and size rules match the strict parser, and the regenerated diff still goes through
parse_unified_diff, _bind and git apply. A hunk whose old block is absent or ambiguous is never rescued.
"""
from dataclasses import dataclass
import difflib
import json
import re

from vgar.repair.patch import _name

NO_EOL = '\\ No newline at end of file'


class NormalizationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.stats = {}


@dataclass(frozen=True)
class NormalizedPatch:
    diff: str
    hunks_total: int
    hunks_noop_dropped: int
    hunks_relocated: int


def _file_header_at(lines, i):
    return lines[i].startswith('diff --git ') or (
        lines[i].startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ '))


def _parse(raw, policy):
    """{path: [(old_block, new_block, header_old_start | None)]} with the strict parser's file-level rules."""
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > policy.max_bytes:
        raise ValueError('Diff size limit')
    lines = raw.splitlines()
    if lines and lines[0] == '```diff':
        if lines[-1] != '```':
            raise ValueError('Incomplete fenced diff')
        lines = lines[1:-1]
    i, files, previous = 0, {}, None
    while i < len(lines):
        if lines[i] == '':
            i += 1
            continue
        git_header = None
        if lines[i].startswith('diff --git '):
            git_header = lines[i]
            i += 1
            if i < len(lines) and re.fullmatch(r'index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?', lines[i]):
                i += 1
        if i + 1 >= len(lines) or not lines[i].startswith('--- ') or not lines[i + 1].startswith('+++ '):
            raise ValueError('Expected file headers; extra text/operations are not allowed')
        path = _name(lines[i][4:], 'a')
        # A header repeated for the file just finished is a format slip: its hunks continue that file.
        if _name(lines[i + 1][4:], 'b') != path or (path in files and path != previous):
            raise ValueError('Rename/duplicate file')
        if path not in policy.allowed_paths or any(path == p or path.startswith(p + '/') for p in policy.protected_paths):
            raise ValueError('Protected or unapproved path')
        if git_header and git_header not in (f'diff --git a/{path} b/{path}',
                f'diff --git {json.dumps("a/"+path, ensure_ascii=False)} {json.dumps("b/"+path, ensure_ascii=False)}'):
            raise ValueError('Git header paths disagree')
        i += 2
        hunks = []
        while i < len(lines) and lines[i].startswith('@@'):
            match = re.match(r'@@ -(\d+)', lines[i])
            start, old, new = (int(match[1]) if match else None), [], []
            i += 1
            while i < len(lines) and not lines[i].startswith('@@') and not _file_header_at(lines, i):
                line = lines[i]
                i += 1
                if line == NO_EOL:
                    continue
                if line == '':  # rule 2: a blank body line is empty context
                    old.append('')
                    new.append('')
                elif line[0] in ' -+':
                    if line[0] in ' -':
                        old.append(line[1:])
                    if line[0] in ' +':
                        new.append(line[1:])
                else:
                    raise ValueError('Truncated or malformed hunk')
            while old and new and old[-1] == '' and new[-1] == '':  # trailing blank lines only shorten context
                old.pop()
                new.pop()
            hunks.append((old, new, start))
        if not hunks:
            raise ValueError('No hunks')
        files.setdefault(path, []).extend(hunks)
        previous = path
    if not files:
        raise ValueError('Empty/no-op/over-limit candidate')
    return files


def _diff(path, before, after, ends_newline):
    out, old_at, new_at = [], None, None
    for line in difflib.unified_diff(before, after, 'a/' + path, 'b/' + path, n=3, lineterm=''):
        out.append(line)
        if line.startswith('@@'):
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            old_at = int(match[1]) - (1 if match[2] != '0' else 0)
            new_at = int(match[3]) - (1 if match[4] != '0' else 0)
            continue
        if line.startswith(('---', '+++')) and old_at is None:
            continue
        last_old = line[0] in ' -' and old_at == len(before) - 1
        last_new = line[0] in ' +' and new_at == len(after) - 1
        if not ends_newline and (last_old or last_new):
            out.append(NO_EOL)
        old_at += line[0] in ' -'
        new_at += line[0] in ' +'
    return out


def normalize_unified_diff(raw, root, policy) -> NormalizedPatch:
    counts = {'hunks_total': 0, 'hunks_noop_dropped': 0, 'hunks_relocated': 0}
    try:
        return _normalize(raw, root, policy, counts)
    except NormalizationError as error:
        error.stats = dict(counts)
        raise


def _normalize(raw, root, policy, counts):
    output = []
    for path, hunks in _parse(raw, policy).items():
        text = (root / path).read_bytes().decode('utf-8')
        before = text.splitlines()
        cursor, after = 0, []
        for old, new, start in hunks:
            counts['hunks_total'] += 1
            if old == new:  # rule 3
                counts['hunks_noop_dropped'] += 1
                continue
            if not old:
                raise NormalizationError('CONTEXT_AMBIGUOUS', f'{path}: hunk has no context to anchor it')
            found = [k for k in range(cursor, len(before) - len(old) + 1) if before[k:k + len(old)] == old]
            if not found:  # rule 4: searched only after the previous hunk
                raise NormalizationError('CONTEXT_NOT_FOUND', f'{path}: old block not found after line {cursor}')
            if len(found) > 1:
                raise NormalizationError('CONTEXT_AMBIGUOUS', f'{path}: old block matches {len(found)} places')
            counts['hunks_relocated'] += start is None or found[0] != start - 1
            after.extend(before[cursor:found[0]])
            after.extend(new)
            cursor = found[0] + len(old)
        after.extend(before[cursor:])
        if after != before:
            output.extend(_diff(path, before, after, text.endswith(('\n', '\r'))))
    if not output:  # rule 5
        raise NormalizationError('NO_OP', 'Every hunk is a no-op or leaves its file unchanged')
    return NormalizedPatch('\n'.join(output) + '\n', **counts)
