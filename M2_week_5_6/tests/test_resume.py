import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from m2_retrieval.evaluation import evaluate_manifest
from m2_retrieval.evidence import sha256, write_json


class ResumeTests(unittest.TestCase):
    def prepare(self, root):
        commit = "a" * 40
        content = b"def login(token):\n    return True\n"
        patch = "--- a/auth.py\n+++ b/auth.py\n@@ -2 +2 @@\n-    return True\n+    return False\n"
        archive = root / "data/repositories/archives" / f"demo__demo-{commit}.tar.gz"
        archive.parent.mkdir(parents=True)
        with tarfile.open(archive, "w:gz") as tar:
            member = tarfile.TarInfo(f"demo-{commit}/auth.py")
            member.size = len(content)
            tar.addfile(member, io.BytesIO(content))
        write_json(archive.with_suffix(".json"), {"url": f"https://codeload.github.com/demo/demo/tar.gz/{commit}", "archive_hash": sha256(archive.read_bytes()), "base_commit": commit})
        patch_path = root / "data/gold/demo-1.patch"
        patch_path.parent.mkdir(parents=True)
        patch_path.write_text(patch, encoding="utf-8")
        manifest = root / "manifest.json"
        write_json(manifest, {"dataset_id": "synthetic", "dataset_revision": "fixture", "tasks": [{"instance_id": "demo-1", "repo": "demo/demo", "base_commit": commit,
                              "problem_statement": "login validates token", "query_hash": sha256("login validates token"), "patch_hash": sha256(patch), "gold_patch_path": "data/gold/demo-1.patch"}]})
        return manifest

    def test_resume_preserves_full_task_artifact_not_just_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            first, _ = evaluate_manifest(root, manifest, offline=True)
            resumed, report = evaluate_manifest(root, manifest, offline=True, resume=first)
            task = json.loads((resumed / "tasks/demo-1.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "SUCCEEDED")
            self.assertIn("context", task)
            self.assertIn("gold", task)
            self.assertTrue((resumed / "m1_requests/demo-1.json").exists())

    def test_resume_rejects_changed_manifest_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            first, _ = evaluate_manifest(root, manifest, offline=True)
            manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                evaluate_manifest(root, manifest, offline=True, resume=first)


if __name__ == "__main__":
    unittest.main()
