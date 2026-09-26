"""Isolated import entry point for the trusted, pinned CCDD engine."""
import json
from pathlib import Path
import sys


def main():
    try:
        engine, contract = map(Path, sys.argv[1:])
        import yaml
        import jsonschema
        schema = json.loads((engine / 'task_contract.schema.json').read_text(encoding='utf-8'))
        jsonschema.Draft202012Validator.check_schema(schema)
        sys.path.insert(0, str(engine / 'runners'))
        import task_gate
        if Path(task_gate.__file__).resolve() != (engine / 'runners/task_gate.py').resolve():
            raise ValueError('Unexpected engine module')
        result = task_gate.gate(str(contract))
        result['runtime'] = {'python': sys.version.split()[0], 'mcp_loaded': any('mcp' in k for k in sys.modules)}
    except Exception as exc:
        result = {'verdict': 'ERROR', 'stage': 'worker', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
