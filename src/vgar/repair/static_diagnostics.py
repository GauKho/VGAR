"""Structured static evidence and conservative, baseline-relative multiset matching."""
import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vgar.repair.contracts import safe_path
from vgar.repair.evidence import digest


class Diagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra='forbid')
    tool: Literal['syntax', 'mypy', 'ruff']
    path: str
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    code: str = Field(min_length=1)
    severity: Literal['error', 'warning', 'note']
    message: str = Field(min_length=1)


class DiagnosticReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    execution_status: Literal['COMPLETE', 'ERROR']
    tool: str
    tool_version: str
    config_hash: str = ''
    scope: tuple[str, ...] = ()
    scope_hash: str = ''
    interpreter_ref: str = ''
    diagnostics: tuple[Diagnostic, ...] = ()
    raw_output_hash: str = ''
    reason: str | None = None


class DiagnosticDelta(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    complete: bool
    status: Literal['PASS', 'FAIL', 'ERROR']
    introduced: tuple[Diagnostic, ...] = ()
    resolved: tuple[Diagnostic, ...] = ()
    persisting: tuple[Diagnostic, ...] = ()
    unmatched: tuple[Diagnostic, ...] = ()
    reason: str | None = None
    identity_version: Literal['m2-static-delta-v1'] = 'm2-static-delta-v1'


def scope_digest(scope):
    return digest(json.dumps(sorted(scope), separators=(',', ':')))


def parse_tool_report(tool: str, command: dict, tool_version: str) -> DiagnosticReport:
    """Parse Ruff JSON / mypy JSON-lines; never interpret lost output as zero errors.

    command.diagnostic_context is host-supplied config/scope/interpreter binding.
    All raw output stays in the owning command record, linked by content hash.
    """
    values = {'tool': tool, 'tool_version': tool_version,
              'raw_output_hash': digest(json.dumps({k: command.get(k) for k in ('stdout', 'stderr')},
                                                  ensure_ascii=False, sort_keys=True))}
    diagnostics = []
    try:
        if tool not in ('mypy', 'ruff') or not isinstance(tool_version, str) or not tool_version.strip():
            raise ValueError('Unsupported tool or missing observed version')
        context = command['diagnostic_context']
        scope = tuple(sorted(safe_path(p) for p in context['scope']))
        if not scope or len(scope) != len(set(scope)) or context['scope_hash'] != scope_digest(scope):
            raise ValueError('Invalid static scope binding')
        for key in ('config_hash', 'interpreter_ref'):
            if not isinstance(context[key], str) or not context[key]:
                raise ValueError('Missing ' + key)
        values.update(scope=scope, scope_hash=context['scope_hash'],
                      config_hash=context['config_hash'], interpreter_ref=context['interpreter_ref'])
        if (command.get('complete') is not True or command.get('timed_out')
                or command.get('output_truncated') or command.get('exit_code') not in (0, 1)
                or command.get('status') not in ('PASS', 'FAIL') or command.get('stderr')):
            raise ValueError('Tool execution incomplete, unsupported exit, or stderr requires diagnosis')
        root = Path(command['cwd']).resolve()
        raw = command['stdout']
        if not isinstance(raw, str):
            raise TypeError('Missing text output')
        if tool == 'ruff':
            rows = json.loads(raw)
            if not isinstance(rows, list):
                raise ValueError('Ruff output must be a JSON array')
        else:
            rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        for item in rows:
            filename = item['filename' if tool == 'ruff' else 'file']
            if not isinstance(filename, str):
                raise TypeError('Invalid diagnostic path')
            filename = filename.replace('\\', '/')
            path = Path(filename)
            if path.is_absolute():
                filename = path.resolve().relative_to(root).as_posix()
            filename = safe_path(filename)
            if filename not in scope:
                raise ValueError('Diagnostic outside approved scope: ' + filename)
            severity = 'error' if tool == 'ruff' else item['severity']
            code = item['code'] or ('note' if severity == 'note' else '')
            message = item['message'].replace('\r\n', '\n')
            # Strip only workspace prefixes, not symbols, types or meaningful text.
            for prefix in (str(root) + '/', str(root) + '\\', root.as_posix() + '/'):
                message = message.replace(prefix, '')
            line = item['location']['row'] if tool == 'ruff' else item['line']
            if tool == 'ruff':
                column = item['location']['column']
            else:
                column = item['column']
                # Validate before arithmetic: bool + 1 would hide malformed JSON.
                if type(column) is not int or column < 0:
                    raise ValueError('mypy column must be a non-negative integer')
                column += 1
            diagnostics.append(Diagnostic(tool=tool, path=filename, line=line, column=column,
                                          code=code, severity=severity, message=message))
        has_errors = any(d.severity in ('error', 'warning') for d in diagnostics)
        if command['exit_code'] != int(has_errors) or command['status'] != ('FAIL' if has_errors else 'PASS'):
            raise ValueError('Exit/status does not agree with diagnostic output')
        return DiagnosticReport(execution_status='COMPLETE', diagnostics=tuple(diagnostics), **values)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        return DiagnosticReport(execution_status='ERROR', reason=str(error),
                                diagnostics=tuple(diagnostics), **values)


def build_line_map(before: dict[str, str], after: dict[str, str]) -> dict:
    """Map equal, uniquely anchored source lines; repeated lines remain ambiguous.

    This intentionally favors false rejects over declaring an unproven error old.
    Large/unsupported snapshots yield no matches rather than quadratic matching.
    """
    result = {}
    for path in before.keys() & after.keys():
        old, new = before[path].splitlines(), after[path].splitlines()
        result[path] = {}
        if len(old) > 10000 or len(new) > 10000:
            continue
        old_counts, new_counts = Counter(old), Counter(new)
        for block in SequenceMatcher(None, old, new, autojunk=False).get_matching_blocks():
            for offset in range(block.size):
                a, b = block.a + offset, block.b + offset
                if old_counts[old[a]] == new_counts[new[b]] == 1:
                    result[path][a + 1] = b + 1
    return result


def _identity(diagnostic):
    return (diagnostic.tool, diagnostic.path, diagnostic.code,
            diagnostic.severity, diagnostic.message, diagnostic.column)


def compare_diagnostics(before: DiagnosticReport, after: DiagnosticReport, line_map: dict) -> DiagnosticDelta:
    """Compare one tool, with a baseline/post binding and a one-to-one line map."""
    if before.execution_status != 'COMPLETE' or after.execution_status != 'COMPLETE':
        return DiagnosticDelta(complete=False, status='ERROR', reason='STATIC_TOOL_INCOMPLETE')
    binding = ('tool', 'tool_version', 'config_hash', 'scope', 'scope_hash', 'interpreter_ref')
    if any(getattr(before, key) != getattr(after, key) for key in binding):
        return DiagnosticDelta(complete=False, status='ERROR', reason='STATIC_BINDING_CHANGED')
    available = defaultdict(list)
    for item in before.diagnostics:
        mapped = line_map.get(item.path, {}).get(item.line)
        if mapped is not None:
            available[(_identity(item), mapped)].append(item)
    introduced, persisting, unmatched = [], [], []
    matched_ids = set()
    for item in after.diagnostics:
        candidates = available[(_identity(item), item.line)]
        if candidates:
            old = candidates.pop()
            matched_ids.add(id(old))
            persisting.append(item)
        else:
            introduced.append(item)
            if any(_identity(old) == _identity(item) for old in before.diagnostics):
                unmatched.append(item)
    resolved = [item for item in before.diagnostics if id(item) not in matched_ids]
    status = 'FAIL' if any(d.severity in ('error', 'warning') for d in introduced) else 'PASS'
    return DiagnosticDelta(complete=True, status=status, introduced=tuple(introduced),
                           resolved=tuple(resolved), persisting=tuple(persisting), unmatched=tuple(unmatched))
