"""Add explicit host-authored contract examples to the measured pytest session."""
import importlib
import json
from pathlib import Path

import pytest

from vgar.repair.semantic_contract import SemanticContract


def pytest_addoption(parser):
    parser.addoption("--vgar-contract", default=None)


class ContractItem(pytest.Item):
    def setup(self):
        example = self.example
        module = importlib.import_module(example.module)
        expected_path = Path.cwd().joinpath(*example.module.split(".")).with_suffix(".py").resolve(strict=True)
        if not getattr(module, "__file__", None) or Path(module.__file__).resolve(strict=True) != expected_path:
            pytest.fail(f"Contract {example.case_id}: module resolved outside its fixture source", pytrace=False)
        self.function = getattr(module, example.function)

    def runtest(self):
        example = self.example
        observed = self.function(*example.args, **example.kwargs)
        actual = json.dumps(observed, sort_keys=True, allow_nan=False)
        expected = json.dumps(example.expected, sort_keys=True, allow_nan=False)
        if actual != expected:
            pytest.fail(f"Contract {example.case_id}: expected {expected}, observed {actual}", pytrace=False)

    def repr_failure(self, excinfo, style=None):
        return f"{type(excinfo.value).__name__}: {str(excinfo.value)[:500]}"


def pytest_collection_modifyitems(session, config, items):
    payload = config.getoption("--vgar-contract")
    if payload is None:
        return
    contract = SemanticContract.model_validate_json(payload)
    for example in contract.examples:
        item = ContractItem.from_parent(session, name=example.node_id, nodeid=example.node_id)
        item.example = example
        items.append(item)
