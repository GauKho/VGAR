import json
from pathlib import Path
import sys
from .hf_backend import execute

if __name__ == '__main__':
    response = Path(sys.argv[2])
    try:
        result = execute(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
    except Exception as error:
        result = dict(status='ERROR', error_type=type(error).__name__, reason=str(error))
    response.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    raise SystemExit(0 if result['status'] == 'PASS' else 2)

