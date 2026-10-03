import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from m2_retrieval.dataset import read_archive_sources


def make_archive(path, entries):
    with tarfile.open(path, "w:gz") as tar:
        for name, text in entries:
            data = text.encode("utf-8")
            item = tarfile.TarInfo(name)
            item.size = len(data)
            tar.addfile(item, io.BytesIO(data))


class ArchiveTests(unittest.TestCase):
    def test_archive_pins_commit_prefix_and_does_not_execute_code(self):
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "repo.tar.gz"
            make_archive(path, [(f"demo-{commit}/auth.py", "raise RuntimeError('never executed')\n"), (f"demo-{commit}/tests/test_a.py", "assert False")])
            sources, audit = read_archive_sources(path, "demo/demo", commit)
            self.assertEqual(list(sources), ["auth.py"])
            self.assertIn("never executed", sources["auth.py"])
            self.assertEqual(audit["snapshot_commit"], commit)

    def test_wrong_commit_or_traversal_member_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "repo.tar.gz"
            for entries in ([("demo-wrong/auth.py", "x=1")], [(f"demo-{'a'*40}/../evil.py", "x=1")]):
                make_archive(path, entries)
                with self.assertRaises(ValueError):
                    read_archive_sources(path, "demo/demo", "a" * 40)


if __name__ == "__main__":
    unittest.main()
