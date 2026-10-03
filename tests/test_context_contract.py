from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from vgar.contracts.context import ContextPayload, ContextItem, SourceRange
from vgar.contracts import context as shared_context


FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "context_payload.json"


class ContextPayloadContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_is_valid(self) -> None:
        context = ContextPayload.model_validate(self.payload)

        self.assertEqual(context.total_token_count, 48)
        self.assertEqual(context.items[0].path, "src/auth/service.py")

    def test_m1_and_consumers_use_the_same_model_classes(self) -> None:
        self.assertIs(ContextPayload, shared_context.ContextPayload)
        self.assertIs(ContextItem, shared_context.ContextItem)
        self.assertIs(SourceRange, shared_context.SourceRange)

    def test_fixture_round_trip_through_shared_import_is_unchanged(self) -> None:
        context = ContextPayload.model_validate(self.payload)
        shared = shared_context.ContextPayload.model_validate_json(context.model_dump_json())
        self.assertEqual(shared.model_dump(mode="json"), self.payload)

    def test_path_must_be_repository_relative_posix(self) -> None:
        for path in ("C:\\repo\\service.py", "/repo/service.py", "../service.py"):
            with self.subTest(path=path):
                invalid = copy.deepcopy(self.payload)
                invalid["items"][0]["path"] = path
                with self.assertRaises(ValidationError):
                    ContextPayload.model_validate(invalid)

    def test_windows_drive_and_unc_paths_are_rejected_through_both_imports(self) -> None:
        for model in (ContextPayload, shared_context.ContextPayload):
            for path in (
                "C:/repo/service.py",
                "c:service.py",
                "//server/share/service.py",
            ):
                with self.subTest(model=model, path=path):
                    invalid = copy.deepcopy(self.payload)
                    invalid["items"][0]["path"] = path
                    with self.assertRaises(ValidationError):
                        model.model_validate(invalid)

    def test_total_token_count_must_match_items(self) -> None:
        invalid = copy.deepcopy(self.payload)
        invalid["total_token_count"] = 47

        with self.assertRaises(ValidationError):
            ContextPayload.model_validate(invalid)

    def test_payload_must_fit_token_budget(self) -> None:
        invalid = copy.deepcopy(self.payload)
        invalid["token_budget"] = 40

        with self.assertRaises(ValidationError):
            ContextPayload.model_validate(invalid)


if __name__ == "__main__":
    unittest.main()