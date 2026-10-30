# W10 tasks without a trustworthy reproduction test (decided before any run)

| Task | Reason |
|---|---|
| `psf__requests-1724` | The issue is a Python 2.7 `unicode` method name causing UnicodeDecodeError; the testbed is Python 3, where every str is unicode, so no reproduction can fail on base for the reported reason. |
| `pylint-dev__pylint-4970` | The issue says `min-similarity-lines=0` flags every line as duplicate; on the exact base inside the image, `--min-similarity-lines=0` reports no R0801 even for two identical files (and `Similar(min_lines=0)` returns no similarities), so a test written from the issue alone passes on base. Checked 28/10 before any run. |
