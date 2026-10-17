"""Strict modify-only unified diff, all-file preflight, Git apply and attestation."""
from dataclasses import dataclass
import ast
import json
import re

from vgar.repair.contracts import safe_path
from vgar.repair.workspace import inventory
from vgar.repair.diagnostics import exception_details, patch_diagnostics


@dataclass(frozen=True)
class PatchPolicy:
    allowed_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]
    max_bytes: int = 256 * 1024
    max_files: int = 5
    max_changed_lines: int = 500


@dataclass
class ParsedPatch:
    raw: str
    files: dict
    policy: PatchPolicy


def _name(value, prefix):
    if value.startswith('"'):
        value = ast.literal_eval(value)
        try:
            value = value.encode('latin-1').decode('utf-8')
        except (UnicodeError, ValueError):
            pass
    value = value.split('\t')[0]
    if not value.startswith(prefix + '/'):
        raise ValueError('Diff must modify an existing a/b path')
    return safe_path(value[2:])


def parse_unified_diff(raw: str, policy: PatchPolicy) -> ParsedPatch:
    location = {}
    try:
        return _parse_unified_diff(raw, policy, location)
    except Exception as error:
        error.parser_diagnostics = patch_diagnostics(raw, location)
        raise


def _parse_unified_diff(raw, policy, location):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > policy.max_bytes:
        raise ValueError('Diff size limit')
    lines = raw.splitlines()
    if lines and lines[0] == '```diff':
        if lines[-1] != '```':
            raise ValueError('Incomplete fenced diff')
        lines = lines[1:-1]
        location['offset'] = 1
    i, files, changes = 0, {}, 0
    while i < len(lines):
        location['index'] = i
        if lines[i] == '':
            i += 1
            continue
        git_header = None
        if lines[i].startswith('diff --git '):
            git_header = lines[i]
            i += 1
            if i < len(lines) and re.fullmatch(r'index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?', lines[i]):
                i += 1
        location['index'] = i
        if i + 1 >= len(lines) or not lines[i].startswith('--- ') or not lines[i+1].startswith('+++ '):
            raise ValueError('Expected file headers; extra text/operations are not allowed')
        location.update(path=lines[i][4:].removeprefix('a/'), hunk=None,
                        hunk_index=None, expected_counts=None, body_end=None)
        path = _name(lines[i][4:], 'a')
        location['path'] = path
        location['index'] = i + 1
        if _name(lines[i+1][4:], 'b') != path or path in files:
            raise ValueError('Rename/duplicate file')
        location['index'] = i
        if path not in policy.allowed_paths or any(path == p or path.startswith(p + '/') for p in policy.protected_paths):
            raise ValueError('Protected or unapproved path')
        if git_header and git_header not in (f'diff --git a/{path} b/{path}',
                f'diff --git {json.dumps("a/"+path, ensure_ascii=False)} {json.dumps("b/"+path, ensure_ascii=False)}'):
            raise ValueError('Git header paths disagree')
        i += 2
        location['index'] = i
        hunks = []
        while i < len(lines) and lines[i].startswith('@@ '):
            location.update(index=i, hunk=i + location.get('offset', 0),
                            hunk_index=len(hunks) + 1, expected_counts=None, body_end=None)
            match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)', lines[i])
            if not match:
                raise ValueError('Malformed hunk header')
            old, oc, new, nc = (int(match[1]), int(match[2] or 1), int(match[3]), int(match[4] or 1))
            location['expected_counts'] = dict(old=oc, new=nc)
            if (oc and old < 1) or (nc and new < 1):
                raise ValueError('Invalid hunk coordinates')
            header, body, seen_old, seen_new = lines[i], [], 0, 0
            i += 1
            while seen_old < oc or seen_new < nc:
                location['index'] = i
                if i >= len(lines) or not lines[i] or lines[i][0] not in ' +-':
                    raise ValueError('Truncated or malformed hunk')
                line = lines[i]
                seen_old += line[0] in ' -'
                seen_new += line[0] in ' +'
                if seen_old > oc or seen_new > nc:
                    raise ValueError('Hunk counts exceeded')
                changes += line[0] in '+-'
                body.append([line[0], line[1:], False])
                i += 1
                if i < len(lines) and lines[i] == '\\ No newline at end of file':
                    body[-1][2] = True
                    i += 1
            location['body_end'] = i + location.get('offset', 0)
            hunks.append(dict(old=old, oc=oc, new=new, nc=nc, header=header, body=body))
        if not hunks:
            raise ValueError('No hunks')
        files[path] = hunks
    if not files or not changes or len(files) > policy.max_files or changes > policy.max_changed_lines:
        raise ValueError('Empty/no-op/over-limit candidate')
    return ParsedPatch(raw, files, policy)


def _bind(patch, root):
    predicted, transport = {}, []
    for path, hunks in patch.files.items():
        original = (root / path).read_bytes()
        lines = original.decode('utf-8').splitlines(keepends=True)
        newline = '\r\n' if b'\r\n' in original else '\n'
        quote = lambda p: json.dumps(p, ensure_ascii=False) if any(c.isspace() for c in p) else p
        transport.extend(['--- ' + quote('a/' + path) + '\n', '+++ ' + quote('b/' + path) + '\n'])
        output, cursor, delta = [], 0, 0
        for hunk in hunks:
            pos = hunk['old'] - (1 if hunk['oc'] else 0)
            new_pos = hunk['new'] - (1 if hunk['nc'] else 0)
            if pos < cursor or pos > len(lines) or new_pos != pos + delta:
                raise ValueError('Hunk offset does not match exact original/output position')
            output.extend(lines[cursor:pos])
            cursor = pos
            transport.append(hunk['header'] + '\n')
            for sign, content, no_eol in hunk['body']:
                if sign in ' -':
                    if cursor >= len(lines) or lines[cursor].rstrip('\r\n') != content or (not lines[cursor].endswith('\n')) != no_eol:
                        raise ValueError('Original hunk context/removal mismatch')
                    cursor += 1
                if sign in ' +':
                    output.append(content + ('' if no_eol else newline))
                # Bind logical diff text to existing file EOL bytes; never change content/counts.
                transport.append(sign + content + newline)
                if no_eol:
                    transport.append('\\ No newline at end of file\n')
            delta += hunk['nc'] - hunk['oc']
        output.extend(lines[cursor:])
        data = ''.join(output).encode('utf-8')
        if data == original:
            raise ValueError('No-op file change')
        predicted[path] = data
    return predicted, ''.join(transport).encode('utf-8')


def apply_patch(lease, patch: ParsedPatch, executor):
    from vgar.contracts.repair import PatchApplyResult, FailureReason
    lease.patch_evidence = []
    try:
        before = inventory(lease.path)
        expected, bound_diff = _bind(patch, lease.path)
        artifact = lease.private / 'candidate.diff'
        artifact.write_bytes(bound_diff)
        for flags in (('--check', '--index'), ('--index',)):
            result = executor.run(('git', 'apply', *flags, str(artifact)), lease.path, 30)
            lease.patch_evidence.append(result)
            if result['status'] != 'PASS':
                raise ValueError('Git apply rejected full candidate: ' + result['stderr'])
        after = inventory(lease.path)
        changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        if changed != sorted(expected) or any((lease.path/p).read_bytes() != data for p, data in expected.items()):
            raise RuntimeError('Applied bytes differ from parsed patch')
        lease.assert_original()
        lease.applied_diff = executor.run(('git', 'diff', '--cached', '--no-ext-diff', '--no-textconv'), lease.path, 30)
        lease.patch_evidence.append(lease.applied_diff)
        if lease.applied_diff['status'] != 'PASS' or not lease.applied_diff.get('complete', False):
            raise RuntimeError('Applied diff export incomplete: ' + lease.applied_diff['stderr'])
        return PatchApplyResult(status='PASS', patch_applied=True, worktree_id=lease.worktree_id, changed_files=changed)
    except ValueError as error:
        lease.patch_exception = exception_details(error)
        return PatchApplyResult(status='FAIL', patch_applied=False, worktree_id=lease.worktree_id,
                                error=FailureReason(code='PATCH_APPLY_FAILED', message=str(error)))
    except (OSError, RuntimeError) as error:
        lease.patch_exception = exception_details(error)
        return PatchApplyResult(status='ERROR', patch_applied=False, worktree_id=lease.worktree_id,
                                error=FailureReason(code='WORKTREE_ERROR', message=str(error)))

