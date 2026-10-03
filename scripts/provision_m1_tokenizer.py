"""Explicit provisioning of tokenizer-only files from an immutable HF revision."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen


TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt")
MAX_FILE_BYTES = 50 * 1024 * 1024


def verify_file(data: bytes, metadata: dict) -> None:
    if len(data) != metadata["size"]:
        raise ValueError("Downloaded file size differs from pinned repository metadata")
    lfs = metadata.get("lfs")
    if lfs:
        if hashlib.sha256(data).hexdigest() != lfs["sha256"]:
            raise ValueError("Downloaded file differs from upstream LFS SHA256")
    else:
        expected = metadata.get("blobId")
        actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if not expected or actual != expected:
            raise ValueError("Downloaded file differs from upstream git blob identity")


def fetch(url: str) -> tuple[bytes, dict[str, str]]:
    request = Request(url, headers={"User-Agent": "VGAR-M1-tokenizer-provisioning/0.1"})
    with urlopen(request, timeout=120) as response:
        data = response.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Tokenizer file exceeds provisioning size limit")
        return data, dict(response.headers.items())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--assets-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.model_id)
            or any(part in {".", ".."} for part in args.model_id.split("/"))):
        parser.error("model-id must be a Hugging Face namespace/repository ID")
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("revision must be an immutable 40-character commit SHA")
    metadata_url = f"https://huggingface.co/api/models/{args.model_id}/revision/{args.revision}?blobs=true"
    raw, _ = fetch(metadata_url)
    metadata = json.loads(raw)
    if metadata.get("sha") != args.revision:
        raise ValueError("Upstream revision metadata does not match requested commit")
    files = {item["rfilename"]: item for item in metadata["siblings"]}
    destination = args.assets_root.resolve() / args.model_id.split("/")[1] / args.revision
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for name in TOKENIZER_FILES:
        upstream = files[name]
        if not 0 < upstream["size"] <= MAX_FILE_BYTES:
            raise ValueError("Invalid tokenizer asset size in upstream metadata")
        url = f"https://huggingface.co/{args.model_id}/resolve/{args.revision}/{name}"
        target = destination / name
        if target.exists():
            data = target.read_bytes()
            verify_file(data, upstream)
        else:
            data, headers = fetch(url)
            served_revision = next((value for key, value in headers.items() if key.lower() == "x-repo-commit"), None)
            if served_revision and served_revision != args.revision:
                raise ValueError("Server responded with a different repository revision")
            verify_file(data, upstream)
            temporary = destination / (name + ".part")
            temporary.write_bytes(data)
            temporary.replace(target)
        records.append({"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                        "upstream_blob_id": upstream.get("blobId"), "upstream_lfs": upstream.get("lfs"),
                        "source_url": url})
        print(f"Verified {name}: {len(data)} bytes")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"model_id": args.model_id, "revision": args.revision,
                "assets_directory": os.path.relpath(destination, args.manifest.resolve().parent).replace("\\", "/"),
                "metadata_url": metadata_url,
                "files": records, "weights_downloaded": False,
                "counting_policy": "encode-each-snippet:add_special_tokens=false:sum-item-counts"}
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Tokenizer-only manifest: {args.manifest}")


if __name__ == "__main__":
    main()
