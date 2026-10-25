"""Contract-first interface; implementation awaits human baseline approval."""
import json


def validate_workflows(repo_root: str, binary: str | None = None) -> dict:
    raise NotImplementedError('Human-approved baseline required')


if __name__ == '__main__':
    print(json.dumps(dict(ok=False, code='WORKFLOW_SYNTAX_NOT_IMPLEMENTED',
                         files=[], diagnostics=[])))
    raise SystemExit(1)
