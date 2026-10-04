# M1 graph contract

Milestone 1 update: 2026-10-03. The user approved this current graph reference
for the integrated checkout; baseline approval is tracked in
[M1 decision log](m1_contract_decision_log.md). Historical documents in the
sibling docs/plans directory remain evidence of earlier checkpoints.

Implementation: `src/vgar/contracts/schema.py`, `src/vgar/graph/builder.py` and
`src/vgar/graph/sqlite_store.py`. This document describes the integrated tree as
of 2026-10-01. M1 owns graph construction, persistence, queries and retrieval;
M3 consumes graph DTOs and owns MCP transport. Endpoint additions for nested
definitions inside tests are recorded below for shared-contract review.

## Snapshot and fields

A graph document has `repo_key`, `repository_revision`, `graph_version`,
`nodes`, `edges` and `statistics`. There is no public `schema_version`.
`graph_version` identifies a snapshot: SHA-256 over repo key, supplied revision,
resolver mode/profile, sorted repository-relative Python paths and source bytes.
The lexical resolver profile is `lexical-v2`; `--no-jedi` produces a different
snapshot from the Jedi-enabled configuration. It is not a schema version.
For an uncommitted checkout, record the base commit and dirty status alongside
the supplied revision rather than presenting the revision as a clean commit.

Each node contains `id`, `type`, `repo_key`, `name`, `qualified_name`, `path`,
`language`, `range`, `properties`, `content_hash` and `graph_version`.
Source-backed ranges contain `start_line`, `start_col`, `end_line`, `end_col`,
`start_byte` and `end_byte`: lines are one-based; columns and byte offsets are
zero-based UTF-8 offsets; the end is exclusive. Paths use repository-relative
POSIX separators. An external module has no source path/range/hash.

Each edge contains `id`, `type`, `source_id`, `target_id`, `confidence`,
`resolution`, `provenance`, `properties` and `graph_version`. Provenance records
the builder, its version, rule ID, supplied source revision and evidence list.
The current builder leaves the evidence list empty; source-backed CallSite and
Import nodes provide the locations used for inspection. Confidence is a
heuristic strength, not a calibrated probability.

## Vocabulary

| Node | Current extraction |
|---|---|
| Repository | One per document |
| File | Each discovered `.py`; parse status, test-path flag and byte size |
| Module | File module name, package flag; external placeholders for imports |
| Class | Class definition, bases, decorators, abstract flag |
| Function | Function outside a class, including nested functions |
| Method | Function directly inside a class; owner ID and method kind |
| Test | `test_*` function directly in a module/class; framework and command hint |
| Import | Module-level import item, imported name, alias and resolution status |
| CallSite | Call inside a function/method/test, callee expression and candidate count |
| Issue | Task-local sidecar emitted by M1 TaskOverlayBuilder; not added to base snapshot |

Test detection remains name-based and assumes pytest; a `test_*` helper nested
inside a callable is a Function. Imports inside functions are not extracted as
Import nodes yet, but their lexical bindings block incorrect module-name
resolution and Jedi may resolve their calls.

| Edge | Endpoint semantics |
|---|---|
| CONTAINS | Repository → File → Module; Module → Class/Function/Import/Test; Class → Method/Test/Class; Function/Method/Test → Function/Class/CallSite |
| IMPORTS | Import → Module; includes external module placeholders |
| INHERITS | Class → Class; internal resolved bases |
| CALLS | CallSite → Function/Method/Class |
| TESTS | Test → File/Module/Class/Function/Method; builder emits direct-call target links |
| REFERENCES | Module/Class/Function/Method/Test/Import/CallSite → File/Module/Class/Function/Method; not emitted yet |
| MENTIONS | Issue → File/Module/Class/Function/Method/Test; task overlay emits links to grounded anchors |
| REPRODUCES | Test → Issue; task overlay emits unambiguous reported failing-test links, not runtime verification |

The 2026-10-01 fix adds only `CONTAINS: Test → Function` and `Test → Class`
to the validator's endpoint table. A nested definition remains owned by the
containing test, following the same representation as ordinary functions.
Repeated calls from a test retain distinct CallSite/CALLS records but share
one TESTS edge per test/target pair, with the greatest supporting confidence.
This does not measure runtime coverage.

## Identity

- Repository: `vgar:{repo_key}:repository`.
- File: `vgar:{repo_key}:python:file:{path}`.
- Module: `vgar:{repo_key}:python:module:{path}:{module_name}`; external modules
  use `vgar:{repo_key}:python:module:external:{module_name}`.
- Class/Function/Method/Test: `vgar:{repo_key}:python:{kind}:{path}:{qualified_name}`.
- Import and CallSite IDs additionally encode source location/occurrence using
  the builder's deterministic rules. These occurrence IDs may change after
  edits within a function or import statement.
- Edge ID: SHA-256 of edge type, source ID, target ID and rule ID, separated by NUL.

Named symbol IDs survive body-only edits while path/name remain unchanged;
rename/move changes identity. IDs are scoped by repo key. Source roots default
to `src`; qualified names remove that prefix and package `__init__` suffix.

## Resolution and validation

The resolver consults Python lexical symbol tables before module definitions.
Nested callable/class definitions can shadow globals; parameters, assignments
and local imports prevent a confident same-name module fallback. Closure
lookup skips class namespaces. Jedi is consulted for unresolved candidates and
must map to one internal graph symbol. Unresolved calls remain CallSite nodes
with `candidate_count=0`; no fabricated target node is created.

| Binding | Confidence |
|---|---|
| Exact containment/import | 1.0 |
| Same lexical/module scope, direct import, known constructor | 0.95 |
| Dotted import | 0.9 |
| Inheritance | 0.9 |
| Jedi target | 0.85 |
| `self`/`cls` method | 0.8 |
| Unique top-level repository-name fallback | 0.6 |

Nested symbols are excluded from the repository-global name fallback. For a
partial parse that cannot produce a Python symbol table, lexical resolution
is conservative; File nodes still report `parse_status=partial`.

Validation rejects duplicate IDs, missing endpoints, unsupported edge/node
types, invalid ranges/confidences, containment cycles, snapshot mismatches,
self-loops, and mismatched CallSite candidate counts. Construction and SQLite
ingestion both validate; build errors must not be recorded as successful output.

## Queries and context boundary

SQLiteGraphService returns existing `vgar.contracts.graph` DTOs for symbol
search, callers, callees, importers, node lookup, repository summary and bounded
subgraph traversal. Symbol search uses SQL text matching; it is not BM25.
Caller/callee queries project `caller → CallSite → target` into one semantic
relationship and filter confidence (store default 0.60). Importers similarly
project `Module → Import → Module`.

Raw subgraph depth counts stored edges, not semantic caller/callee hops. Current
subgraph limits are depth 0–5 and node limit 1–1000. MCP depth semantics belong
to M3 and have not been changed by this fix.

Graph query errors use the existing shared error classes/fixtures, including
invalid query/limit, unknown symbol/node and graph-not-ready outcomes.
`ContextPayload` requires snapshot, anchors, source snippets/ranges, rationale,
scores/confidence and exact per-item/total token accounting within budget.
Context classes are defined once in `vgar.contracts.context` and re-exported
from `vgar.graph.context` for M1 import compatibility. The 2026-10-03 consolidation
keeps JSON schemas unchanged. See [context contract](context_payload_contract.md)
for actual model constraints and proposed producer/token policies.

### Portable document to query DTO mapping

| Portable graph | GraphNodeRef / GraphEdgeRef | Notes |
|---|---|---|
| Node id / type | node_id / node_type | IDs remain opaque; do not parse fixture IDs to infer the builder convention |
| Node name / qualified_name / path | same named fields | External Module path may be null |
| Node range | source_range | DTO carries start/end line/col, not raw byte offsets |
| Node content_hash / properties | same named fields | DTO does not introduce node-level confidence/provenance |
| Edge id / type | edge_id / edge_type | Endpoint IDs, confidence, resolution, provenance and properties retained |
| Document graph_version / revision | repository summary metadata | Do not add these fields to the existing SymbolRef without consumer review |

SymbolRef remains `symbol_id`, `name`, `kind`, `path`. SearchSymbolsResult is
`query` plus `symbols`; SymbolRelationsResult is `symbol_id` plus `symbols`.
Node details/ranges/properties come from get_node rather than expanded symbol
query fields. Search defaults to 20 hits, accepts limit 1–100 and rejects a blank
query. Runtime errors remain `INVALID_QUERY`, `INVALID_LIMIT`, `NODE_NOT_FOUND`,
`GRAPH_NOT_READY` and the base `GRAPH_ERROR`.

The legacy decision memo's storage threshold 0.30 is not an implemented
ambiguous-candidate policy: the current builder emits known resolved targets
and keeps other call sites unresolved. The validator accepts confidence in 0–1;
query filtering defaults to 0.60. Current TESTS links use direct call evidence;
coverage/import/naming-based links are future work. STALE_GRAPH is proposed in
old notes but is not a current public error code.

## Limits and next step

This is a static approximation. Conditional/repeated definitions, rebinding
after a definition, lambda/comprehension scope, dynamic dispatch, monkey
patching, decorators and complex inheritance may remain unresolved or require
further precision work. It does not establish full Python call-graph correctness.
Use a fresh builder instance for each build. A full successful build proves
validity and stability for that run, not graph precision/recall.

Task grounding and task-local overlays are implemented in `vgar.graph.grounding`
and `vgar.graph.task_overlay`; see `docs/retrieval_design.md`. M1 semantic retrieval
and source-verified packing now live in `vgar.graph.retrieval`; see
[method](m1_retrieval_method.md). Standalone official tokenizer configuration/
token accounting has passed [acceptance](m1_tokenizer_acceptance.md) with 95 tests.
Benchmark retrieval evaluation and M2/M3 integration remain subsequent work.
