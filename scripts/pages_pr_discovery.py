"""Run Pages discovery in a fresh venv using deployment's Python installers."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import venv

try:
    import yaml
except ImportError:
    yaml = None


if yaml is not None:
    class _UniqueLoader(yaml.SafeLoader):
        def compose_node(self, parent, index):
            if self.check_event(yaml.AliasEvent) or self.peek_event().anchor is not None:
                raise yaml.YAMLError('aliases and anchors are not supported')
            return super().compose_node(parent, index)

    def _unique_mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in result:
                raise yaml.YAMLError('duplicate mapping key')
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    _UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)

class PagesError(ValueError):
    def __init__(self, code, message):
        super().__init__(code + ': ' + message)


def _fail(code, message):
    raise PagesError(code, message)


def _workflow(root):
    if yaml is None:
        _fail('PAGES_CONFIGURATION', 'PyYAML is required to inspect deployment')
    path = root / '.github/workflows/deploy-pages.yml'
    try:
        data = yaml.load(path.read_text(encoding='utf-8'), Loader=_UniqueLoader)
        job = data['jobs']['deploy']
        steps = job['steps']
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        raise PagesError('PAGES_CONFIGURATION', 'invalid deployment workflow') from exc
    if not isinstance(data, dict) or not isinstance(job, dict) or not isinstance(steps, list):
        _fail('PAGES_CONFIGURATION', 'invalid deployment structure')
    if job.get('runs-on') != 'ubuntu-latest' or any(key in data for key in ('env', 'defaults')):
        _fail('PAGES_CONFIGURATION', 'unsupported deployment environment')
    if any(key in job for key in ('env', 'defaults', 'container', 'strategy')):
        _fail('PAGES_CONFIGURATION', 'unsupported deployment environment')
    builds = [i for i, step in enumerate(steps)
              if isinstance(step, dict) and step.get('name') == 'Build and validate public bundle']
    if len(builds) != 1:
        _fail('PAGES_CONFIGURATION', 'public build must be unambiguous')
    return steps[:builds[0]]


def _plain_step(step):
    if any(key in step for key in ('if', 'env', 'continue-on-error', 'working-directory')):
        _fail('PAGES_CONFIGURATION', 'conditional or modified preparation step')
    if step.get('shell', 'bash') != 'bash':
        _fail('PAGES_CONFIGURATION', 'unsupported preparation shell')


def _pip_args(step):
    _plain_step(step)
    command = step['run'].strip()
    if re.search(r'[;&|<>`$()\r\n#*?\[\]{}~\\]', command):
        _fail('PAGES_CONFIGURATION', 'nonliteral Python installer')
    try:
        parts = shlex.split(command, posix=True)
    except ValueError as exc:
        raise PagesError('PAGES_CONFIGURATION', 'invalid installer syntax') from exc
    if parts[:4] != ['python', '-m', 'pip', 'install'] or len(parts) == 4:
        _fail('PAGES_CONFIGURATION', 'unsupported Python installer')
    return parts[4:]


def _non_pip_step(step):
    _plain_step(step)
    expected = {
        'Install pinned publisher': 'npm ci --prefix site --ignore-scripts --no-audit --no-fund',
        'Verify Pages build contract': 'python -m unittest tests/test_pages_build.py\npython scripts/validate_contracts.py knowledge/contracts',
    }
    command = '\n'.join(line.strip() for line in step['run'].strip().splitlines())
    if expected.get(step.get('name')) != command:
        _fail('PAGES_CONFIGURATION', 'unsupported deployment preparation step')


def _installers(steps):
    commands, python_versions = [], []
    allowed_actions = ('actions/checkout@', 'actions/setup-python@',
                       'actions/setup-node@', 'actions/download-artifact@')
    for step in steps:
        if not isinstance(step, dict):
            _fail('PAGES_CONFIGURATION', 'invalid deployment step')
        if 'uses' in step:
            _plain_step(step)
            action = step['uses']
            if not isinstance(action, str) or not action.startswith(allowed_actions):
                _fail('PAGES_CONFIGURATION', 'unsupported preparation action')
            if action.startswith('actions/setup-python@'):
                options = step.get('with', {})
                if not isinstance(options, dict) or set(options) != {'python-version'}:
                    _fail('PAGES_CONFIGURATION', 'invalid Python setup')
                python_versions.append(options.get('python-version'))
        elif isinstance(step.get('run'), str):
            if re.search(r'\bpip\b', step['run'], re.IGNORECASE):
                commands.append(_pip_args(step))
            else:
                _non_pip_step(step)
        else:
            _fail('PAGES_CONFIGURATION', 'unsupported deployment step')
    if python_versions != ['3.11'] or sys.version_info[:2] != (3, 11) or not commands:
        _fail('PAGES_CONFIGURATION', 'deployment Python or installers differ')
    return commands


def _environment(root, requested):
    path = Path(requested).absolute()
    if os.path.lexists(path):
        _fail('PAGES_ENVIRONMENT', 'venv destination already exists')
    resolved = path.resolve()
    if resolved == root or resolved.is_relative_to(root):
        _fail('PAGES_ENVIRONMENT', 'venv must be outside checkout')
    try:
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(resolved)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise PagesError('PAGES_ENVIRONMENT', 'could not create venv') from exc
    return resolved / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def _run(command, root, environment, code):
    try:
        result = subprocess.run(command, cwd=root, env=environment, capture_output=True,
                                text=True, encoding='utf-8', errors='backslashreplace', timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise PagesError(code, 'process could not complete') from exc
    if result.returncode:
        _fail(code, (result.stderr or result.stdout or 'process failed').strip())
    return result.stdout


def _discovery(python, root, environment):
    raw = _run([str(python), '-I', '-X', 'utf8', str(root / 'site/ci_inventory.py'),
                'discover', '--repo-root', str(root)], root, environment, 'PAGES_DISCOVERY')
    try:
        ids = json.loads(raw)
    except ValueError as exc:
        raise PagesError('PAGES_DISCOVERY', 'invalid discovery output') from exc
    if (not isinstance(ids, list) or not ids or any(not isinstance(item, str) or not item for item in ids)
            or ids != sorted(set(ids)) or any('_FailedTest' in item for item in ids)):
        _fail('PAGES_DISCOVERY', 'incomplete or invalid inventory')
    return ids


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True)
    parser.add_argument('--venv-dir', required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(args.repo_root).resolve(strict=True)
        if not root.is_dir():
            _fail('PAGES_CONFIGURATION', 'repository root is not a directory')
        commands = _installers(_workflow(root))
        python = _environment(root, args.venv_dir)
        environment = dict(os.environ, PYTHONNOUSERSITE='1', PYTHONUTF8='1')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
        for command in commands:
            _run([str(python), '-I', '-m', 'pip', 'install', *command], root, environment, 'PAGES_INSTALL')
        ids = _discovery(python, root, environment)
        print(json.dumps({'ok': True, 'tests': len(ids), 'ids': ids}, ensure_ascii=True))
        return 0
    except PagesError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError) as exc:
        print('PAGES_CONFIGURATION: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())