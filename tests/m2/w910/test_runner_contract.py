"""Direct/session/MCP boundary evidence, not an implementation of M3 runner."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIX = '--- a/auth.py\n+++ b/auth.py\n@@ -1,2 +1,2 @@\n def login(value):\n-    return bool(value)\n+    return bool(value.strip())\n'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))
