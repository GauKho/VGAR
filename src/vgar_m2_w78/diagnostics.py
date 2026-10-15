"""Internal diagnostics only; never repair input or capture exception locals."""
import traceback


def exception_details(error):
    details = dict(type=type(error).__name__, message=str(error),
                   traceback=''.join(traceback.TracebackException.from_exception(
                       error, capture_locals=False).format(chain=True)))
    if hasattr(error, 'parser_diagnostics'):
        details['parser_diagnostics'] = error.parser_diagnostics
    return details


def patch_diagnostics(raw, location):
    lines = raw.splitlines() if isinstance(raw, str) else []
    index = location.get('index', 0) + location.get('offset', 0)
    hunk = location.get('hunk')
    expected = location.get('expected_counts')
    actual, invalid, ambiguous = None, [], None
    if expected is not None:
        actual = dict(old=0, new=0)
        end = location.get('body_end')
        for n in range(hunk + 1, len(lines)):
            text = lines[n]
            if text.startswith('@@ ') or text == '```' or text.startswith('diff --git '):
                break
            if ((end is None or n >= end) and text.startswith(('--- a/', '--- "a/')) and n + 1 < len(lines)
                    and lines[n + 1].startswith(('+++ b/', '+++ "b/'))):
                # A failed/incomplete hunk could contain header-like source text.
                # Do not claim a complete count when the boundary is ambiguous.
                if end is None:
                    ambiguous = dict(raw_line=n + 1, reason='Possible next file header in incomplete hunk')
                break
            if text == '\\ No newline at end of file':
                continue
            if not text and all(not line for line in lines[n:]):
                break
            if not text:
                following = next((line for line in lines[n + 1:] if line), '')
                if following.startswith(('--- ', 'diff --git ', '@@ ')) or following == '```':
                    break
            if not text or text[0] not in ' +-':
                if end is not None and n >= end:
                    break
                invalid.append(dict(raw_line=n + 1, text=text))
            else:
                actual['old'] += int(text[0] in ' -')
                actual['new'] += int(text[0] in ' +')
    return dict(raw_line=index + 1, raw_line_text=lines[index] if index < len(lines) else None,
        raw_line_count=len(lines), path=location.get('path'), hunk_index=location.get('hunk_index'),
        hunk_raw_line=hunk + 1 if hunk is not None else None,
        hunk_header=lines[hunk] if hunk is not None else None, expected_counts=expected,
        actual_counts=actual, counts_complete=actual is not None and not invalid and ambiguous is None,
        invalid_body_lines=invalid, ambiguous_body_boundary=ambiguous,
        counts_note='Actual counts use valid body prefixes only; invalid lines are not guessed or repaired')
