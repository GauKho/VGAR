import json
from pathlib import Path
import sys
from vgar.models.huggingface.hf_backend import execute
from vgar.repair.diagnostics import exception_details
from vgar.repair.evidence import atomic_json


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    response = Path(argv[1])
    try:
        result = execute(json.loads(Path(argv[0]).read_text(encoding='utf-8')),
                         diagnostics_path=response.parent / 'generation_diagnostics.json')
    except Exception as error:
        result = dict(status='ERROR', error_type=type(error).__name__, reason=str(error), **exception_details(error))
    atomic_json(response, result)
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())

