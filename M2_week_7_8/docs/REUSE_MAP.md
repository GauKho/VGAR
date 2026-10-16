# Reuse map

Source reference: VGAR `b8e2461635b81d1ae790445efea5c9757d91700a`, read-only.
Raw boundary hashes are in `config/source_pin.json`; bootstrap rejects unexpected changes.
Existing retrieval/scoring dirty diffs are preserved, not used to fake a new source revision.

| Original | Use in M2 | Boundary |
|---|---|---|
| contracts/context, consumer, handoff, prompt_context | Import verified public APIs, not copy | No graph rebuilding or schema modification |
| contracts/repair, evidence | Import public DTO projection | Internal richer records stay separate |
| repair/test_runner.py | Adapt bounded stdout polling, Windows job/process-group cleanup concept | Add exact pytest IDs, fail-closed reporting, close/kill descendant handling |
| repair/workspace.py | Adapt normalized path/inventory guards | New private seed + Git worktree, source .git never touched |
| repair/evidence_writer.py | Adapt atomic pending/final unique records | Full stage details and append-only invocation directories |
| tests/fixtures/w7_w8_handoff | Byte-identical copies with input receipt | Original .py/tests/pytest.ini protected; no oracle in prompt |

