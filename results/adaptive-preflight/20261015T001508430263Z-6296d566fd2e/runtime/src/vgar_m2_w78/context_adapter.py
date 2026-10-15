"""Thin verified consumer, retaining original sidecars and diagnostics."""
from dataclasses import dataclass
import json

from .bootstrap import verify_reference
from .evidence import digest


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


def load_handoff(task, m1_counter, counter_label) -> ValidatedHandoff:
    verify_reference()
    from vgar.contracts.consumer import HandoffTarget, receive_context_handoff
    from vgar.contracts.context import ContextPayload
    names = ('context.json', 'context_manifest.json', 'test_links.json')
    raw = {name: (task.bundle_directory / name).read_bytes() for name in names}
    result = receive_context_handoff(task.bundle_directory, task.source_repo,
        HandoffTarget(task_id=task.task_id, repo_key=task.repo_key,
                      repository_revision=task.revision, graph_version=task.graph_version),
        count_tokens=m1_counter, counter_label=counter_label)
    value = ValidatedHandoff(task, ContextPayload.model_validate(result['context']),
        result['context_text'], result['test_inputs'], result['metadata'],
        json.loads(raw['context_manifest.json']), json.loads(raw['test_links.json']),
        {name: digest(data) for name, data in raw.items()})
    value.assert_unchanged()
    return value

