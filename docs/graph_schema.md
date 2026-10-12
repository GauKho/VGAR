# M1 graph contract

Graph reference for M1. Earlier milestone decisions are tracked in
[M1 decision log](m1_contract_decision_log.md). Historical documents in the
sibling docs/plans directory remain evidence of earlier checkpoints.

Implementation: `src/vgar/contracts/schema.py`, `src/vgar/graph/builder.py` and
`src/vgar/graph/sqlite_store.py`. M1 owns graph construction, persistence,
queries and retrieval; M3 consumes graph DTOs and owns MCP transport.
Endpoint additions for nested definitions inside tests are recorded below
for shared-contract review.

## Snapshot and fields

A graph document has `repo_key`, `repository_revision`, `graph_version`,
`nodes`, `edges` and `statistics`. There is no public `schema_version`.
`graph_version` identifies a snapshot: SHA-256 over repo key, supplied revision,
resolver/range profiles, source roots, sorted repository-relative Python paths
and source bytes. The resolver profile is `tree-sitter+python-static-v3-method-aliases` and the
file-range profile is `full-bytes-v1`. The builder does not use Jedi. These
profiles are not schema versions.
Direct, unambiguous class method aliases are stored in the implementation's
`properties.symbol_aliases`, with qualified names and assignment-token ranges.
They map API names to the original implementation, without duplicate nodes.
Optional SCIP enrichment adds `scip-enrichment-v5-subset-root` and a root-independent digest
of indexed occurrences to the snapshot identity. The exact binary index and
source inventory are bound by a checksummed bundle; stale bundles are rejected.
When `target_only` indexing emits the configured subset as its index root,
document paths are rebased to the repository. The subset must be explicitly
recorded and match that root; traversal, absolute paths and foreign roots are
rejected. Full source/config snapshot checks still apply to partial indexes.
`scip-python` 0.6.6 uses legacy UTF-16 columns and native Windows separators;
the adapter converts these to repository-relative POSIX paths and UTF-8 bytes.
Non-UTF-8 documents are omitted from SCIP mapping without transcoding source;
other documents remain usable. `definition_mapping.skipped_documents` and
`resolver_document_skipped` events record the affected paths and reason. This
does not add non-UTF-8 snippet support to the graph contract.
SCIP CALLS edges have `binding_kind="scip"`, confidence 0.98 and indexer provenance.
Indexer failure/no occurrence uses the static fallback with recorded reasons.
External/ambiguous bindings remain unresolved. A classmethod `cls()` parameter
may use a conservative static constructor fallback at 0.80 when not reassigned.
The W5–W6 resolver extension also supports direct LSP definition requests via
Pyright 1.1.414. `LspConfig` enables this in the builder; CLI modes are `lsp` and
`scip-lsp`. Only missing or weak static bindings are queried, within request and
time limits. Verified SCIP bindings, including external/ambiguous bindings,
are not overridden. LSP targets must match internal declaration or alias name
tokens in the unchanged source/config/stub snapshot. External, non-callable or
ambiguous answers remain unresolved; absent answers or infrastructure failure
allow static fallback. LSP CALLS edges have `binding_kind="lsp"`, policy
confidence 0.95 and server provenance. `candidate_count` still counts CALLS
edges; unresolved alternatives use `lsp_candidate_count`, not CALLS edges.
The `lsp-definition-v1` snapshot profile includes actual answers and runtime
hashes. `statistics.resolver.lsp` records server, statuses, limits and failures;
JSONL has `lsp_start`, `lsp_ready`, `lsp_call_result`, `lsp_fallback` and
`lsp_complete`. LSP stderr is saved separately. These diagnostics do not write
source text to MCP stdout. Plot tracking distinguishes LSP from SCIP/static.
LSP does not execute target code or verify runtime dispatch, and controlled
fixture results do not establish benchmark-wide precision or retrieval gains.
When a chained member has no SCIP occurrence but its inner getter is resolved,
source return annotations or a simple getter backed by an `isinstance`-guarded
setter can produce `REFERENCES` hints to the declared type and known overrides.
These hints have heuristic confidence 0.65, source evidence and
`runtime_dispatch_verified=false`. They leave the CallSite unresolved and do
not create CALLS or TESTS edges. Conflicting writes, shadowed guards, unknown
types and more than 16 candidate methods disable the hint.
For an uncommitted checkout, record the base commit and dirty status alongside
the supplied revision rather than presenting the revision as a clean commit.

Each node contains `id`, `type`, `repo_key`, `name`, `qualified_name`, `path`,
`language`, `range`, `properties`, `content_hash` and `graph_version`.
Source-backed ranges contain `start_line`, `start_col`, `end_line`, `end_col`,
`start_byte` and `end_byte`: lines are one-based; columns and byte offsets are
zero-based UTF-8 offsets; the end is exclusive. Paths use repository-relative
POSIX separators. An external module has no source path/range/hash.

File and source-backed Module ranges cover the full file bytes, including
leading whitespace, and their content hashes cover the same bytes.

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
| Test | `test_*` function directly in a module/class in a test path; framework and command hint |
| Import | Module-level import item, imported name, alias and resolution status |
| CallSite | Call inside a function/method/test, callee expression and candidate count |
| Issue | Task-local sidecar emitted by M1 TaskOverlayBuilder; not added to base snapshot |

Test detection remains name-based and assumes pytest; a `test_*` helper nested
inside a callable is a Function. Imports inside functions are not extracted as
Import nodes yet, but their lexical bindings block incorrect module-name
resolution; their calls may remain unresolved.

| Edge | Endpoint semantics |
|---|---|
| CONTAINS | Repository → File → Module; Module → Class/Function/Import/Test; Class → Method/Test/Class; Function/Method/Test → Function/Class/CallSite |
| IMPORTS | Import → Module; includes external module placeholders |
| INHERITS | Class → Class; internal resolved bases |
| CALLS | CallSite → Function/Method/Class |
| TESTS | Test → File/Module/Class/Function/Method; builder emits direct-call target links |
| REFERENCES | Module/Class/Function/Method/Test/Import/CallSite → File/Module/Class/Function/Method; source-backed return-contract hints from unresolved chained CallSites |
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
- Repeated definitions and property accessors may have additional ID suffixes
  to distinguish nodes with the same qualified name.
- Import and CallSite IDs additionally encode source location/occurrence using
  the builder's deterministic rules. These occurrence IDs may change after
  edits within a function or import statement.
- Edge ID: SHA-256 of edge type, source ID, target ID and rule ID, separated by NUL.

Named symbol IDs without occurrence suffixes survive body-only edits while
path/name remain unchanged; rename/move changes identity. IDs are scoped by
repo key. Source roots default
to `src`; qualified names remove that prefix and package `__init__` suffix.

## Resolution and validation

The resolver consults Python lexical symbol tables before module definitions.
Nested callable/class definitions can shadow globals; parameters, assignments
and local imports prevent a confident same-name module fallback. Closure
lookup skips class namespaces. Explicit parameter annotations can resolve
method calls when they map to an internal class and the parameter is not
reassigned. Unresolved calls remain CallSite nodes
with `candidate_count=0`; no fabricated target node is created.

| Binding | Confidence |
|---|---|
| Exact containment/import | 1.0 |
| Same lexical/module scope, direct import, known constructor | 0.95 |
| Dotted import | 0.9 |
| Inheritance | 0.9 |
| Method on an explicitly typed internal-class parameter | 0.85 |
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
subgraph limits are depth 0–5 and node limit 1–1000. MCP caller/callee tools
return direct relationships; their depth argument does not enable multi-hop
queries.

Task grounding and context retrieval take an explicit `graph_version` and
`task_id`. Task overlays are request-local. Context retrieval uses semantic
hops, verifies source bytes against the snapshot and requires a repository
root and a verified local tokenizer. Legacy SQLite snapshots without stored
source ranges must be rebuilt before context retrieval.

Graph query errors use the existing shared error classes/fixtures, including
invalid query/limit, unknown symbol/node and graph-not-ready outcomes.
`ContextPayload` requires snapshot, anchors, source snippets/ranges, rationale,
scores/confidence and exact per-item/total token accounting within budget.
Context classes are defined once in `vgar.contracts.context` and re-exported
from `vgar.graph.context` for M1 import compatibility. The 2026-10-03 consolidation
keeps JSON schemas unchanged. See [context contract](context_payload_contract.md)
for actual model constraints and proposed producer/token policies.

The MCP context response wrapper labels this shape as `vgar.context.v1` through
`context_format`; it also carries `repository_revision` and per-node
`source_metadata` (content hash and range encoding). These are sidecar fields,
not extra properties on the frozen ContextPayload. The M2 prompt adapter is
`vgar.contracts.prompt_context.render_context_for_repair`. Prompt headers and
instructions are outside the snippet-only token budget.

`get_related_tests` takes explicit `graph_version`, symbol IDs and/or changed
paths. Direct TESTS links can be followed through reverse CALLS, with bounded
hops/visited nodes. Returned selectors include static evidence/confidence,
truncation and traversal flags. Supplied failing tests are retained; without
links the selector uses failing tests, then supplied selected tests. With none
it returns `requires_full_suite=true`. This API selects candidates only: M2
owns test execution, suite policy and verification. It does not claim coverage.

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
[method](m1_retrieval_method.md). Standalone tokenizer configuration and token
accounting are described in [acceptance](m1_tokenizer_acceptance.md).
MCP exposes task grounding and budgeted context retrieval through graph tools.
Benchmark scripts compare graph retrieval with BM25; results depend on the
selected task population and repository snapshot.
