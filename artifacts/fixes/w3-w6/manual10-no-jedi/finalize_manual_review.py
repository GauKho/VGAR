"""Bundle the authored interpretation and unchanged collected cards, not a rerun."""
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src'))
from vgar.evaluation.retrieval.evidence import new_run, sha256, utc_now, write_json


def main():
    root = Path(__file__).resolve().parents[4]
    cards = root / 'artifacts/fixes/w3-w6/manual10-no-jedi/evidence/20261007T020305188540Z-617ca4415d05/result.json'
    report = root / 'docs/reviews/2026-10-07-manual-retrieval-audit-10.md'
    directory, record = new_run(root / 'artifacts/fixes/w3-w6/manual10-no-jedi/completed', 'manual-retrieval-self-review')
    started = time.perf_counter()
    original = cards.read_bytes()
    reviews = json.loads(original)
    assert reviews['status'] == 'PASS' and len(reviews['reviews']) == 10
    assert len({card['instance_id'] for card in reviews['reviews']}) == 10
    report_raw = report.read_bytes()
    content = report_raw.decode('utf-8')
    assert all(card['instance_id'] in content for card in reviews['reviews'])
    record.update(status='PASS', complete=True, exit_code=0, ended_utc=utc_now(),
                  duration_seconds=time.perf_counter() - started, inference='NOT_RUN',
                  reviewer='Codex self-review, not independent or owner sign-off',
                  manual_review_completed=True,
                  selection=reviews.get('selection'),
                  collected_evidence_path=str(cards), collected_evidence_sha256=sha256(original),
                  report_path=str(report), report_sha256=sha256(report_raw), report_markdown=content,
                  collected_evidence=reviews,
                  collection_preserved=cards.read_bytes() == original)
    write_json(directory / 'result.json', record)
    print(directory / 'result.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
