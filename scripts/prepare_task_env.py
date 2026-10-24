"""W9-5 Docker-only task environment qualification entry point."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from vgar.evaluation.harness.task_env import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
