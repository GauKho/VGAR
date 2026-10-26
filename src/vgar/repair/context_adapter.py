"""Thin verified consumer, retaining original sidecars and diagnostics."""
from dataclasses import dataclass
import json

from vgar.repair.evidence import digest


@dataclass
class ValidatedHandoff:
    task: object
    context: object
    context_text: str
    inputs: dict
    metadata: dict
    manifest: dict
    hints: dict
    hashes: dict

    def assert_unchanged(self):
        for name, expected in self.hashes.items():
            path = self.task.bundle_directory / name
            if not path.is_file() or digest(path.read_bytes()) != expected:
                raise ValueError('Handoff bundle changed after validation: ' + name)


def load_handoff(task, m1_counter, counter_label, *, arm=None, expected_hashes=None) -> ValidatedHandoff:
    from vgar.contracts.consumer import HandoffTarget, receive_context_handoff
    from vgar.contracts.context import ContextPayload
    from vgar.repair.experiment import validate_hashes
    if arm is not None and (not isinstance(arm, str) or arm not in ('bm25', 'graph')):
        raise ValueError('Unknown retrieval arm')
    expected_hashes = validate_hashes(expected_hashes)
    names = ('context.json', 'context_manifest.json', 'test_links.json')
    raw = {name: (task.bundle_directory / name).read_bytes() for name in names}
    hashes = {name: digest(data) for name, data in raw.items()}
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError('Handoff differs from expected bundle hashes')
    result = receive_context_handoff(task.bundle_directory, task.source_repo,
        HandoffTarget(task_id=task.task_id, repo_key=task.repo_key,
                      repository_revision=task.revision, graph_version=task.graph_version),
        count_tokens=m1_counter, counter_label=counter_label)
    value = ValidatedHandoff(task, ContextPayload.model_validate(result['context']),
        result['context_text'], result['test_inputs'], result['metadata'],
        json.loads(raw['context_manifest.json']), json.loads(raw['test_links.json']),
        hashes)
    if arm is not None:
        value.metadata['arm'] = arm  # Caller-declared label; not proof of retrieval algorithm.
    value.assert_unchanged()
    return value

