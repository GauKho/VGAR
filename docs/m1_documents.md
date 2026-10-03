# M1 document index

Date: 2026-10-03. User-approved document source arrangement for the integrated
VGAR checkout; consumer sign-off remains separate in the M1 decision log.

## Current checkout references

| Purpose | Reference |
|---|---|
| Graph shapes, IDs, endpoints, queries/errors and DTO mapping | [graph_schema.md](graph_schema.md) |
| Context models, validation and approved M1 producer principles | [context_payload_contract.md](context_payload_contract.md) |
| User-approved Milestone 1 baseline decisions | [m1_contract_decision_log.md](m1_contract_decision_log.md) |
| Approval state and remaining sign-off | [m1_contract_decision_log.md](m1_contract_decision_log.md) |
| Direct module boundaries and shared effects on M2/M3 | [m1_change_scope_2026-10-03.md](m1_change_scope_2026-10-03.md) |
| Current deliverables, setup and graph handoff | [m1_handoff_2026-10-03.md](m1_handoff_2026-10-03.md) |
| 01/10 build/source-review evidence | [graph_quality_report.md](graph_quality_report.md) |
| Implemented grounding and remaining retrieval work | [retrieval_design.md](retrieval_design.md) |
| Milestone 2 task overlay checkpoint evidence | [task-grounding manifest](../artifacts/m1/task-grounding/manifest.json) |
| Milestone 3 retrieval evidence before official token counting | [context-retrieval manifest](../artifacts/m1/context-retrieval/manifest.json) |
| Traversal/ranking/source/token policy and CLI | [m1_retrieval_method.md](m1_retrieval_method.md) |
| Approved tokenizer configuration and scope | [m1_tokenizer_acceptance.md](m1_tokenizer_acceptance.md) |
| Official tokenizer acceptance, hashes/runtime and run commands | [m1_tokenizer_acceptance.md](m1_tokenizer_acceptance.md) |

Executable definitions: `src/vgar/contracts/schema.py`,
`src/vgar/contracts/context.py`, `src/vgar/contracts/graph.py` and
`src/vgar/contracts/error.py`. M1 implementation is under `src/vgar/graph`.
Fixtures under `tests/fixtures/contracts` verify DTO shape; the builder owns
the actual NodeID convention. `scripts/run_m1_tests.py` checks this checkout.

## Sibling documents retained as research/history

| Evidence | Reference |
|---|---|
| Ten core research papers and design traceability | [literature matrix](../../docs/plans/M1_week1_literature_evidence_matrix.md) |
| Extended literature review | [research review](../../docs/plans/M1_literature_review_CPG_repository_graph_retrieval.md) |
| Prior graph schema and open consumer decisions | [29/09 schema](../../docs/plans/graph_schema.md) |
| Older decision memo and implementation baseline | [decision memo](../../docs/plans/M1_week1_schema_decision_memo.md) |
| Prior manual review: 31 CALLS/IMPORTS edges | [edge review](../../docs/plans/M1_manual_edge_validation.md) |
| Prior integration smoke and handoff | [SQLite/MCP checkpoint](../../docs/plans/M1_M3_sqlite_integration_checkpoint_2026-09-29.md) |
| Proposed meeting confirmation, not completed minutes | [meeting presentation](../../docs/plans/M1_meeting_presentation_report_2026-09-29.md) |

Do not mix historical metrics/IDs with current snapshots. Earlier schema 1.0.0
language, MAY_CALL/SCIP plans and draft error names are proposals/history, not
requirements to add fields/dependencies to the current contract. Refer to the
decision log and current contracts for reconciled choices. User approval of M1 decisions must not
be presented as M2/M3 sign-off or a completed project-wide protocol freeze.
