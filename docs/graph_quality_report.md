# M1 graph quality checkpoint — 2026-10-01

Base commit: `2491a047638c183a6d6adee41c8a8f79b8b9020d`, branch
`integrated-w3-w4-m1-m2-m3-20260930`; the measured checkout includes uncommitted
M1 fixes and grounding work. Builds use revision label `2491a047-worktree-m1`,
source root `src` and resolver profile `lexical-v2`.

## Runtime and verification

Windows CPython 3.12.14 at `D:\KLTN\M1\.venv-win\Scripts\python.exe`, with
VGAR/src first on the import path; Tree-sitter 0.25.2, Python grammar 0.25.0,
Jedi 0.20.0. Tree-sitter was updated in that environment, not only in pyproject.
Other virtual environments still need their dependencies synchronized separately.

**46 M1 tests pass**, including graph schema, extraction/resolution, regression
cases, ContextPayload validation, SQLite/DTO compatibility, end-to-end fixture
pipeline and task anchors. This is a scoped M1 suite, not a claim that the full
model/agent/M2/M3 test suite was executed.

Both full-repository modes successfully construct and validate a graph. The
Jedi snapshot was ingested into SQLite and checked via summary, search,
caller/callee and subgraph queries. Sample-repository construction also passes.

| Snapshot | Files | Nodes | Edges | CALLS | Unresolved / call sites | Partial files | Build time (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| VGAR, no Jedi | 98 | 2683 | 3452 | 360 | 1346 / 1706 | 0 | 241.678 |
| VGAR, Jedi | 98 | 2683 | 3562 | 432 | 1274 / 1706 | 0 | 18504.435 |
| Sample fixture, no Jedi | 8 | 40 | 52 | 5 | 2 / 7 | 0 | 9.783 |

Times are one observed run per mode, measured by the builder before final
validation/output; they are not a repeated latency benchmark. Resolution rate
counts emitted targets; it is not graph recall. External/builtin calls and
unsupported dynamic behavior contribute to unresolved counts.

## Source inspection sample

[edge_review.csv](../artifacts/m1/graph-quality/edge_review.csv) records **20
source-inspected edges, all matching the expected target**. Review was performed
by Codex against the source statements and target definitions; a human peer
review/sign-off is still separate. Each row includes source text/path/line,
expected and actual target, decision, rationale, edge ID and graph snapshot.

Sampling: first five CALLS and five IMPORTS in each of the sample fixture and
VGAR no-Jedi graph, sorted by source path, line and edge ID. VGAR samples are
restricted to `src/vgar/graph`; import statements are deduplicated by
path/line/target module. The sample covers relative/internal imports, external
standard-library imports, classmethod constructors, `self` calls, constructors,
imported functions and calls from tests. It is deliberately small and ordered;
it does not estimate population precision or recall.

Regression tests separately cover nested-function/parameter/assignment/local
import shadowing, closure bindings, class namespace behavior, nested classes,
nested `test_*` helpers, repeated test calls and exclusion of nested symbols
from the repository-global fallback. These expected cases are not relabeled as
manual graph edges or benchmark tasks.

## Evidence

- [Build metrics/config/runtime](../artifacts/m1/graph-quality/build_metrics.json).
- [M1 test log](../artifacts/m1/graph-quality/tests.txt).
- [SQLite smoke output](../artifacts/m1/graph-quality/sqlite_smoke.json).
- [Task anchor smoke output](../artifacts/m1/graph-quality/anchor_smoke.json).

Large full graph JSON/SQLite files remain in the local report directory
`D:\KLTN\reports\vgar_m1_20261001\crash_diagnosis`; exact paths, hashes and
snapshot IDs are in build_metrics.json. They are not required by runtime code
and can be regenerated with the handoff commands.

## Remaining quality work

Expand source annotations to less predictable bindings, unresolved eligible
calls, local imports, aliases, inheritance and dynamic cases across an additional
independent Python repository. Annotating only emitted edges cannot establish
recall. The fixture is the second source tree checked here; no external benchmark
repository or SWE-bench evaluation has been claimed.

Grounding is an initial W5–W6 component. Task overlays, semantic traversal,
ranking, tokenizer-based ContextPayload packing and Graph-versus-BM25 evaluation
remain pending. This checkpoint repairs the known build blockers and does not
declare the entire retrieval milestone complete.
