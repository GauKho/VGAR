"""Put the repository's src/, ablation_matrix/ and scripts/ on sys.path; baseline/ only imports from them."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _part in ("scripts", "ablation_matrix", "src"):
    if str(ROOT / _part) not in sys.path:
        sys.path.insert(0, str(ROOT / _part))
