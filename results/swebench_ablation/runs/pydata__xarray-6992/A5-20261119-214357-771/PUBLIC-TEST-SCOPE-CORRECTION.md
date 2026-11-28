# Correction to public test scope

The earlier `results.md`, `evaluation-summary.json` and operator README described the public test runtime as a sentinel. That was an incorrect inference from the admission profile. Runtime execution uses `execution.public_scope('pydata__xarray-6992')`: `xarray/tests/test_dataset.py`.

Read-only inspection of actual same-final-diff A5 evidence `public-tests-684ca18683ba4202b4c0f45b10a4bb5d.json` confirms370PASS,1XFAIL,1XPASS,1SKIP. The admission sentinel and actual public test scope are distinct. The official evaluator results remain unchanged: resolved=false, FAIL_TO_PASS0/12, PASS_TO_PASS945/945. Five public semantic contracts and graph checks also passed in their stated scope; they did not establish official resolution.

This addendum supersedes only the inaccurate sentinel wording. Existing sealed reports are retained as history; this new addendum is not included in their original48-file checksum manifest. Evidence and read-only diagnostic script are in `D:/Project/CAPSTONES/VGAR/results/swebench_ablation/manual_sessions/20261119-xarray6992-a0-guide/bridge-evidence-inspection.json` and `bridge-findings.md`. No model, test or grading rerun was performed for this correction.
