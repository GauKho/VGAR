"""Run a repository-native test runner (Django runtests, sympy bin/test) and write the pytest report contract.

Copied into the SWE-bench container and run by the testbed interpreter, so this file is Python 3.5+
and stdlib only: no f-strings, no annotations. The upstream command comes from --command-json
(pinned SWE-bench test_cmd for the task's repo/version); this file only adds labels or files.
Report keys are exactly those of vgar.repair.pytest_plugin, with pytest-style node IDs.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from xml.sax.saxutils import quoteattr

RUNNERS = ('django_runtests', 'sympy_bin_test')
DJANGO_STATUS = {'ok': 'PASS', 'FAIL': 'FAIL', 'ERROR': 'ERROR', 'skipped': 'SKIP',
                 'expected failure': 'XFAIL', 'unexpected success': 'XPASS'}
# Not anchored: Django 1.11 can append a result to an unrelated migration line. The optional middle
# line is a docstring's first line. Python >= 3.11 prints "(module.Class.test_name)".
DJANGO_RESULT = re.compile(r'(\w+) \(([\w.]+)\)(?:\n[^\n]*?)? \.\.\. '
                           r'(ok|FAIL|ERROR|skipped|expected failure|unexpected success)')
SYMPY_STATUS = {'ok': 'PASS', 'F': 'FAIL', 'E': 'ERROR', 'f': 'XFAIL', 's': 'SKIP', 'X': 'XPASS', 'T': 'ERROR'}
SYMPY_FILE = re.compile(r'^(\S+\.py)\[(\d+|\?)\]')
SYMPY_RESULT = re.compile(r'^(test_\w+) (ok|F|E|f|s|X|T)\b')


def _split(selector):
    parts = selector.split('::')
    if not parts[0].endswith('.py') or any(not p for p in parts):
        raise ValueError('Invalid selector: ' + selector)
    return parts[0], parts[1:]


def django_label(selector):
    path, rest = _split(selector)
    if not path.startswith('tests/'):
        raise ValueError('Django runtests labels live under tests/: ' + selector)
    return '.'.join([path[len('tests/'):-len('.py')].replace('/', '.')] + rest)


def sympy_file(selector):
    path, rest = _split(selector)
    if len(rest) > 1:
        raise ValueError('sympy tests are module-level functions: ' + selector)
    return path


def parse_django(log):
    outcomes, errors = {}, []
    for match in DJANGO_RESULT.finditer(log):
        name, dotted, result = match.groups()
        if dotted.endswith('.' + name):
            dotted = dotted[:-len(name) - 1]
        if 'unittest.loader._FailedTest' in dotted or '.' not in dotted or not name.startswith('test'):
            errors.append(match.group(0))
            continue
        module, cls = dotted.rsplit('.', 1)
        outcomes['tests/' + module.replace('.', '/') + '.py::' + cls + '::' + name] = DJANGO_STATUS[result]
    errors.extend(line for line in log.splitlines() if line.startswith('ImportError: Failed to import test module'))
    return outcomes, errors


def parse_sympy(log):
    outcomes, errors, current = {}, [], None
    for line in log.splitlines():
        header = SYMPY_FILE.match(line)
        if header:
            current = header.group(1)
            if header.group(2) == '?' or 'Failed to import' in line:
                errors.append(line.strip())
            continue
        result = SYMPY_RESULT.match(line)
        if result and current:
            outcomes[current + '::' + result.group(1)] = SYMPY_STATUS[result.group(2)]
    return outcomes, errors


def _selected(node_id, selectors):
    return any(node_id == s or node_id.startswith(s + '::') for s in selectors)


def _junit(outcomes):
    cases = []
    for node_id, status in sorted(outcomes.items()):
        path, _, name = node_id.rpartition('::')
        body = {'FAIL': '<failure/>', 'ERROR': '<error/>', 'SKIP': '<skipped/>'}.get(status, '')
        cases.append('<testcase classname=%s name=%s>%s</testcase>' % (quoteattr(path), quoteattr(name), body))
    return '<testsuite name="vgar-native" tests="%d">%s</testsuite>\n' % (len(cases), ''.join(cases))


def _write(path, text):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, 'w', encoding='utf-8') as stream:
        stream.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner', choices=RUNNERS, required=True)
    parser.add_argument('--command-json', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--junit', required=True)
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('selectors', nargs='+')
    args = parser.parse_args(argv)
    command = json.loads(args.command_json)
    if args.runner == 'django_runtests':
        targets = sorted(set(django_label(s) for s in args.selectors))
    else:
        targets = sorted(set(sympy_file(s) for s in args.selectors))
    env = dict(os.environ)
    env.update(command['env'])
    # Separate pipes: interleaved stdout/stderr is what breaks result lines in Django 1.11.
    process = subprocess.Popen([sys.executable] + command['argv'] + targets, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env)
    out, err = process.communicate()
    out, err = out.decode('utf-8', 'replace'), err.decode('utf-8', 'replace')
    sys.stdout.write(out + err)
    parse = parse_django if args.runner == 'django_runtests' else parse_sympy
    outcomes, errors = parse(err + '\n' + out)
    outcomes = dict((k, v) for k, v in outcomes.items() if _selected(k, args.selectors))
    node_ids = sorted(outcomes)
    if not node_ids or errors:
        code = 2
    elif args.collect_only:
        code = 0
    else:
        code = 1 if any(v in ('FAIL', 'ERROR') for v in outcomes.values()) else 0
    report = {'node_ids': node_ids, 'outcomes': outcomes, 'durations_ms': dict((n, 0) for n in node_ids),
              'collection_errors': errors, 'complete': True, 'exit_code': code}
    _write(args.report, json.dumps(report, indent=2, sort_keys=True))
    _write(args.junit, _junit(outcomes))
    return code


if __name__ == '__main__':
    sys.exit(main())
