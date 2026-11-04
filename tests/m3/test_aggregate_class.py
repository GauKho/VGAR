"""Trace spec 2026-11-03 §6.2 (plan Task 9): aggregate counts outcome classes and warns MIXED_CODE when the
attempts of one experiment ran on different VGAR code."""
import json

from test_aggregate import run, stored  # noqa: F401 (fixture)


def _set_code(stored, heads):  # noqa: F811
    path, data, out, grades = stored
    # every attempt of the experiment; the last head repeats (a record missing `code` counts as 'unknown')
    files = sorted(out.glob('*/attempts/*/attempt-1.json'))
    for i, file in enumerate(files):
        head = heads[min(i, len(heads) - 1)]
        record = json.loads(file.read_text(encoding='utf-8'))
        record['code'] = {'head': head * 40, 'dirty': []}
        file.write_text(json.dumps(record), encoding='utf-8')


def test_rows_and_variants_carry_classes(stored):  # noqa: F811
    summary, markdown = run(stored)
    rows = {(r['task_id'], r['variant_id']): r['class'] for r in summary['rows']}
    assert rows[('demo__demo-1', 'A0')] == 'MODEL' and rows[('demo__demo-1', 'A1')] == 'VERIFIED'
    assert rows[('demo__demo-1', 'A2')] == 'NOT_RUN' and rows[('demo__demo-2', 'A0')] == 'PROTOCOL'
    assert summary['variants']['A0']['classes'] == {'MODEL': 1, 'PROTOCOL': 1}
    assert '| A0 | MODEL | 1 |' in markdown and '| variant | class | count |' in markdown


def test_records_without_code_are_unknown_not_mixed(stored):  # noqa: F811
    summary, markdown = run(stored)
    assert summary['code'] == {'heads': ['unknown'], 'mixed': False}
    assert 'Code: unknown' in markdown and 'MIXED_CODE' not in markdown


def test_same_head_is_not_mixed(stored):  # noqa: F811
    _set_code(stored, ['a', 'a', 'a'])
    summary, markdown = run(stored)
    assert summary['code']['mixed'] is False and 'MIXED_CODE' not in markdown


def test_two_heads_are_mixed_code(stored):  # noqa: F811
    _set_code(stored, ['a', 'b'])
    summary, markdown = run(stored)
    assert summary['code']['mixed'] is True and set(summary['code']['heads']) >= {'a' * 7, 'b' * 7}
    assert '**MIXED_CODE**' in markdown
