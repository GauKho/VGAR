from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from vgar.graph.context import ContextPayload


FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "context_payload.json"


class ContextPayloadContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_is_valid(self) -> None:
        context = ContextPayload.model_validate(self.payload)

        self.assertEqual(context.total_token_count, 48)
        self.assertEqual(context.items[0].path, "src/auth/service.py")

    def test_path_must_be_repository_relative_posix(self) -> None:
        invalid = copy.deepcopy(self.payload)
        invalid["items"][0]["path"] = "C:\\repo\\service.py"

        with self.assertRaises(ValidationError):
            ContextPayload.model_validate(invalid)

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
