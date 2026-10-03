"""M1 offline counter integrity and full-length snippet accounting regressions."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vgar.graph.token_counter import COUNTING_POLICY, LocalTokenizerCounter


@unittest.skipUnless(importlib.util.find_spec("tokenizers"), "Optional M1 tokenizer runtime is not provisioned")
class LocalTokenizerCounterTests(unittest.TestCase):
    def setUp(self):
        from tokenizers import Tokenizer, models, pre_tokenizers, processors
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.path = self.root / "manifest.json"
        self.native = Tokenizer(models.WordLevel({"[UNK]": 0, "[CLS]": 1, "hello": 2, "世界": 3}, unk_token="[UNK]"))
        self.native.pre_tokenizer = pre_tokenizers.Whitespace()
        self.native.add_special_tokens(["[CLS]"])
        self.native.post_processor = processors.TemplateProcessing(single="[CLS] $A", special_tokens=[("[CLS]", 1)])
        self.native.enable_truncation(max_length=3)
        self.native.enable_padding(length=8)
        (self.assets / "tokenizer.json").write_text(self.native.to_str(), encoding="utf-8")
        for name, data in (("tokenizer_config.json", "{}"), ("vocab.json", "{}"), ("merges.txt", "# test")):
            (self.assets / name).write_text(data, encoding="utf-8")
        self.manifest = {
            "model_id": "fixture/tokenizer", "revision": "a" * 40, "assets_directory": "assets",
            "counting_policy": COUNTING_POLICY, "weights_downloaded": False,
            "files": [{"name": path.name, "size": path.stat().st_size,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in self.assets.iterdir()],
        }
        self.write_manifest()

    def write_manifest(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_full_length_unicode_crlf_empty_and_literal_special_tokens(self):
        counter = LocalTokenizerCounter(self.path)
        self.native.no_truncation()
        self.native.no_padding()
        for text in ("", "hello", "hello\r\n世界", "hello " * 50, "[CLS] hello", "đếm token 🐻"):
            with self.subTest(text=text[:30]):
                self.assertEqual(counter(text), len(self.native.encode(text, add_special_tokens=False).ids))
        self.assertEqual(counter(""), 0)
        self.assertEqual(counter("hello " * 50), 50)
        self.assertEqual(counter("[CLS] hello"), 2)  # Literal text is counted, no prefix is added.
        self.assertIn("@" + "a" * 40, counter.counter_label)
        self.assertEqual(counter.provenance["tokenizers_version"], "0.22.1")
        with self.assertRaises(TypeError):
            counter(None)

    def test_each_asset_tamper_is_rejected(self):
        for record in self.manifest["files"]:
            target = self.assets / record["name"]
            original = target.read_bytes()
            target.write_bytes(original + b" ")
            with self.subTest(name=target.name), self.assertRaisesRegex(ValueError, "size/hash mismatch"):
                LocalTokenizerCounter(self.path)
            target.write_bytes(original)

    def test_same_size_corruption_is_rejected(self):
        target = self.assets / "vocab.json"
        target.write_bytes(b"[]")
        with self.assertRaisesRegex(ValueError, "size/hash mismatch"):
            LocalTokenizerCounter(self.path)

    def test_missing_or_extra_asset_is_rejected(self):
        target = self.assets / "vocab.json"
        target.unlink()
        with self.assertRaisesRegex(ValueError, "exactly the approved"):
            LocalTokenizerCounter(self.path)
        target.write_text("{}", encoding="utf-8")
        (self.assets / "model.safetensors").write_bytes(b"not weights")
        with self.assertRaisesRegex(ValueError, "exactly the approved"):
            LocalTokenizerCounter(self.path)

    def test_unpinned_revision_wrong_policy_and_duplicate_records_fail(self):
        original = copy.deepcopy(self.manifest)
        for key, value in (("revision", "main"), ("weights_downloaded", True), ("counting_policy", "words"),
                           ("model_id", "not-a-model-id"), ("assets_directory", None),
                           ("files", [original["files"][0]] * 4)):
            self.manifest = {**original, key: value}
            self.write_manifest()
            with self.subTest(key=key), self.assertRaises(ValueError):
                LocalTokenizerCounter(self.path)

    def test_loaded_counter_keeps_verified_bytes_if_disk_changes(self):
        counter = LocalTokenizerCounter(self.path)
        (self.assets / "tokenizer.json").write_text("tampered", encoding="utf-8")
        self.assertEqual(counter("hello " * 20), 20)
        with self.assertRaisesRegex(ValueError, "size/hash mismatch"):
            LocalTokenizerCounter(self.path)

    def test_runtime_version_drift_is_explicit(self):
        import tokenizers
        with patch.object(tokenizers, "__version__", "different"), self.assertRaisesRegex(RuntimeError, "requires tokenizers==0.22.1"):
            LocalTokenizerCounter(self.path)

    def test_cli_emits_shared_payload_and_rejects_tampered_assets(self):
        from vgar.graph.builder import PythonGraphBuilder
        repository = self.root / "repository"
        repository.mkdir()
        (repository / "sample.py").write_text('def hello():\n    return "世界"\n', encoding="utf-8")
        graph_path = self.root / "graph.json"
        graph_path.write_text(json.dumps(PythonGraphBuilder(repo_key="counter-test", repository_revision="fixture",
                                                           use_jedi=False).build(repository)), encoding="utf-8")
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/get_related_context.py"),
                   str(graph_path), str(repository), "--budget-tokens", "8000", "--issue-text", "sample.py:1",
                   "--tokenizer-manifest", str(self.path)]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertNotIn("tokenizer_provenance", payload)  # Shared fields stay unchanged.
        self.assertTrue(payload["items"])
        self.native.no_padding()
        self.native.no_truncation()
        self.assertEqual(payload["total_token_count"], sum(len(self.native.encode(item["snippet"], add_special_tokens=False).ids)
                                                         for item in payload["items"]))
        (self.assets / "vocab.json").write_bytes(b"[]")
        rejected = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("size/hash mismatch", rejected.stderr)
        self.assertFalse(rejected.stdout)


class TokenizerProvisioningIntegrityTests(unittest.TestCase):
    def test_upstream_blob_and_lfs_hashes_detect_corruption(self):
        script = Path(__file__).resolve().parents[1] / "scripts/provision_m1_tokenizer.py"
        spec = importlib.util.spec_from_file_location("m1_tokenizer_provisioner", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = b"tokenizer only"
        for upstream in ({"size": len(data), "blobId": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()},
                         {"size": len(data), "lfs": {"sha256": hashlib.sha256(data).hexdigest()}}):
            module.verify_file(data, upstream)
            with self.assertRaises(ValueError):
                module.verify_file(b"X" + data[1:], upstream)
            with self.assertRaises(ValueError):
                module.verify_file(data + b"X", upstream)
