"""Offline M1 snippet counter with pinned, hash-verified tokenizer assets."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


TOKENIZER_FILES = {"tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt"}
COUNTING_POLICY = "encode-each-snippet:add_special_tokens=false:sum-item-counts"
RUNTIME_VERSION = "0.22.1"


class LocalTokenizerCounter:
    """Load once from a manifest; retrieval never downloads files or model weights."""

    def __init__(self, manifest_path: str | Path) -> None:
        path = Path(manifest_path).resolve()
        raw = path.read_bytes()
        manifest = json.loads(raw)
        if not isinstance(manifest, dict):
            raise ValueError("Tokenizer manifest must be an object")
        model_id = manifest.get("model_id")
        revision = manifest.get("revision")
        if not isinstance(model_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", model_id):
            raise ValueError("Manifest needs a namespace/repository model ID")
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("Manifest revision must be an immutable 40-character commit SHA")
        if manifest.get("weights_downloaded") is not False or manifest.get("counting_policy") != COUNTING_POLICY:
            raise ValueError("Manifest must describe tokenizer-only assets and the M1 counting policy")
        directory = manifest.get("assets_directory")
        if not isinstance(directory, str) or not directory:
            raise ValueError("Manifest needs assets_directory")
        assets = Path(directory)
        if not assets.is_absolute():
            assets = path.parent / assets
        assets = assets.resolve()
        records = manifest.get("files")
        if (not isinstance(records, list) or len(records) != len(TOKENIZER_FILES)
                or any(not isinstance(record, dict) or not isinstance(record.get("name"), str) for record in records)
                or {record["name"] for record in records} != TOKENIZER_FILES):
            raise ValueError("Manifest must list exactly the four tokenizer assets")
        # Unknown files (including weights) must not be mistaken for this verified bundle.
        if {entry.name for entry in assets.iterdir()} != TOKENIZER_FILES:
            raise ValueError("Tokenizer directory must contain exactly the approved tokenizer files")
        for record in records:
            target = (assets / record["name"]).resolve()
            if target.parent != assets:
                raise ValueError("Tokenizer file resolves outside the assets directory")
            data = target.read_bytes()
            digest = record.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Manifest needs a SHA256 for every tokenizer file")
            if len(data) != record.get("size") or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Tokenizer asset size/hash mismatch: {record['name']}")
            if record["name"] == "tokenizer.json":
                tokenizer_bytes = data
        try:
            import tokenizers
        except ImportError as error:
            raise RuntimeError("Install the isolated M1 tokenizer runtime before loading the counter") from error
        if tokenizers.__version__ != RUNTIME_VERSION:
            raise RuntimeError(f"M1 counter requires tokenizers=={RUNTIME_VERSION}; got {tokenizers.__version__}")
        try:
            self._tokenizer = tokenizers.Tokenizer.from_str(tokenizer_bytes.decode("utf-8"))
        except Exception as error:
            raise ValueError(f"Cannot parse verified tokenizer.json: {error}") from error
        # Saved tokenizer settings must never truncate or pad the snippet accounting.
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()
        tokenizer_hash = next(record["sha256"] for record in records if record["name"] == "tokenizer.json")
        self.counter_label = f"local-hf:{model_id}@{revision}:sha256={tokenizer_hash}:no-special-tokens"
        self.provenance = {
            "model_id": model_id, "revision": revision, "tokenizer_json_sha256": tokenizer_hash,
            "manifest_sha256": hashlib.sha256(raw).hexdigest(), "tokenizers_version": tokenizers.__version__,
            "counting_policy": COUNTING_POLICY, "padding": False, "truncation": False,
        }

    def __call__(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError("Snippet must be a string")
        return len(self._tokenizer.encode(text, add_special_tokens=False).ids)