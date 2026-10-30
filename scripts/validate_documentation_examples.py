"""Extract and run the actual red/green examples from the quickstart."""
import argparse
import json
from pathlib import Path
import re
import tempfile

from oracle_execution import execute_oracle
from validate_contracts import parse_frontmatter, validate_file, _calculate_tests_hash


def _block(text, label, language):
    if label not in text:
        raise ValueError('Documented step missing: ' + label)
    match = re.search(r'```' + language + r'\n(.*?)\n```', text.split(label, 1)[1], re.S)
    if match is None:
        raise ValueError('Documented code sample missing: ' + label)
    return match.group(1) + '\n'


def _contract(template, fields):
    frontmatter, body = parse_frontmatter(template)
    # Keep canonical sections, so a broken template also breaks this example.
    body = body.split('<!--', 1)[0]
    body = re.sub(r'<[^\n>]+>', 'documented-example', body)
    header = {key: frontmatter[key] for key in ('type', 'title', 'description', 'tags')}
    header.update(title='Saludar', description='Ejemplo ejecutado del tutorial', tags=['ccdd', 'example'])
    header.update(fields)
    lines = ['---']
    for key, value in header.items():
        if isinstance(value, dict):
            lines.append(key + ':')
            lines.extend('  ' + name + ': ' + str(limit) for name, limit in value.items())
        else:
            lines.append(key + ': ' + (json.dumps(value, ensure_ascii=False) if isinstance(value, (str, list)) else str(value)))
    return '\n'.join(lines) + '\n---\n' + body


def verify_documentation_examples(repo_root):
    """Verify the documented oracle, stub, implementation and field example."""
    result = {'ok': False}
    try:
        root = Path(repo_root).resolve()
        quickstart = (root / 'knowledge/quickstart.md').read_text(encoding='utf-8')
        template = (root / 'knowledge/contracts/TEMPLATE-task-contract.md').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory(prefix='kdd-docs-') as directory:
            project = Path(directory)
            (project / 'tests').mkdir()
            (project / 'src').mkdir()
            (project / 'tests/__init__.py').write_text('', encoding='utf-8')
            oracle = project / 'tests/test_saludar.py'
            oracle.write_text(_block(quickstart, '**4.1', 'python'), encoding='utf-8')
            target = project / 'src/saludar.py'
            target.write_text(_block(quickstart, '**4.3', 'python'), encoding='utf-8')
            fields, _ = parse_frontmatter('---\n' + _block(quickstart, '**4.4', 'yaml') + '---\n')
            fields['tests_sha256'] = _calculate_tests_hash(oracle)
            contract = project / 'saludar.md'
            contract.write_text(_contract(template, fields), encoding='utf-8')
            result['contract_findings'] = [str(item) for item in validate_file(contract, project)]
            result['stub'] = execute_oracle(fields, project, 10)
            target.write_text(_block(quickstart, '**4.6', 'python'), encoding='utf-8')
            result['implemented'] = execute_oracle(fields, project, 10)
            result['ok'] = (not result['contract_findings'] and not result['stub']['ok']
                            and 'NotImplementedError' in result['stub']['stderr']
                            and result['implemented']['ok'] and result['implemented']['executed_tests'] == 2)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result['error'] = str(exc)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    args = parser.parse_args(argv)
    result = verify_documentation_examples(args.repo_root)
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
