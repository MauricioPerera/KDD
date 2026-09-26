"""Native, opt-in CCDD adapter. Trusted code only; not a sandbox."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

if __package__:
    from . import validate_contracts as validator
else:
    import validate_contracts as validator

ENGINE_COMMIT = 'e6073e124ca506da6750aa41485350b717b2ff28'
CAPS = {'cyclomatic_max': 20, 'nesting_max': 4, 'lines_max': 80, 'params_max': 5}
RESOURCES = ('runners/task_gate.py', 'runners/tc_lint.py', 'task_contract.schema.json',
             'contracts/task-author-agent/thresholds.txt',
             'contracts/complexity-agent/thresholds.txt')


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inside(root, value):
    path = (root / value).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError('Path outside repo root')
    return path


def prepare(contract, repo_root):
    root = Path(repo_root).resolve(strict=True)
    path = _inside(root, Path(contract).resolve(strict=True))
    findings = validator.validate_file(str(path), repo_root=str(root))
    if any(f.level == 'ERROR' for f in findings):
        raise ValueError('Level 1 contract or LF seal invalid')
    metadata, body = validator.parse_frontmatter(path.read_text(encoding='utf-8'))
    if metadata.get('kind', 'function') != 'function' or metadata.get('language', 'python') != 'python':
        raise ValueError('Native profile supports Python function contracts only')
    budget = {k: int(v) for k, v in metadata['budget'].items()}
    if any(k not in CAPS or type(v) is not int or not 0 < v <= CAPS[k] for k, v in budget.items()):
        raise ValueError('Budget outside native profile caps')
    metadata['budget'] = {**CAPS, **budget}
    for key in ('require_test_approval', 'enforce_deps', 'pure', 'forbid_mutable_defaults',
                'forbid_bare_except', 'forbid_assert', 'forbid_none_eq', 'require_issue'):
        if key in metadata:
            if metadata[key] not in ('true', 'false'):
                raise ValueError('Boolean options require true or false')
            metadata[key] = metadata[key] == 'true'
    if 'target_line' in metadata:
        metadata['target_line'] = int(metadata['target_line'])
    target, tests = (_inside(root, metadata[k]) for k in ('target', 'tests'))
    cwd = _inside(root, metadata.get('test_cwd', '.'))
    if not cwd.is_dir() or not target.is_file() or not tests.is_file():
        raise ValueError('Invalid target, tests or test_cwd')
    seal = hashlib.sha256(tests.read_bytes().replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()
    if seal != metadata['tests_sha256']:
        raise ValueError('LF test seal mismatch')
    metadata.update(target=target.relative_to(root).as_posix(), tests=tests.relative_to(root).as_posix(),
                    test_cwd=cwd.relative_to(root).as_posix(), require_test_approval=True,
                    tests_sha256=_hash(tests))
    return {'metadata': metadata, 'body': body, 'paths': [path, target, tests],
            'tests_sha256_lf': seal}


def _git(engine, args):
    result = subprocess.run(['git', '-C', str(engine), *args], capture_output=True,
                            text=True, encoding='utf-8', timeout=15, check=True)
    return result.stdout.strip()


def verify_engine(engine):
    engine = Path(engine).resolve(strict=True)
    if _git(engine, ['rev-parse', 'HEAD']) != ENGINE_COMMIT:
        raise ValueError('Engine revision differs from pinned commit')
    if _git(engine, ['status', '--porcelain', '--untracked-files=normal']):
        raise ValueError('Engine checkout is not clean')
    for resource in RESOURCES:
        path = _inside(engine, resource)
        if not path.is_file():
            raise ValueError('Required engine resource missing')
    return ENGINE_COMMIT


def _stop(process):
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
        finally:
            if process.poll() is None:
                process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def _invoke(command, timeout, cwd):
    env = dict(os.environ)
    env['PATH'] = str(Path(command[0]).parent) + os.pathsep + env.get('PATH', '')
    env['PYTHONUTF8'] = '1'
    with tempfile.TemporaryFile() as output:
        with subprocess.Popen(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.DEVNULL,
                              start_new_session=os.name != 'nt') as process:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                _stop(process)
                raise TimeoutError('Native gate timed out') from exc
            if process.returncode != 0:
                raise ValueError('Native worker failed')
        output.seek(0)
        raw = output.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('Native result too large')
    result = json.loads(raw)
    if not isinstance(result, dict) or result.get('verdict') not in ('PASS', 'FAIL', 'INVALID', 'ERROR'):
        raise ValueError('Invalid native result')
    return result


def _export(prepared, root):
    # JSON scalars/collections are valid YAML; preserve Unicode and test_command.
    text = '---\n' + ''.join(k + ': ' + json.dumps(v, ensure_ascii=False) + '\n'
                             for k, v in prepared['metadata'].items())
    text += '---\n' + prepared['body']
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                     prefix='kdd-native-', suffix='.gate.md', dir=root,
                                     delete=False) as stream:
        stream.write(text)
        return Path(stream.name)


def run_level2(contract, repo_root, engine_root, *, python=None, timeout=120):
    started = time.monotonic()
    result = {'ok': False, 'verdict': 'ERROR', 'stage': 'preflight', 'engine_commit': ENGINE_COMMIT}
    exported = None
    try:
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Timeout must be positive and finite')
        root = Path(repo_root).resolve(strict=True)
        prepared = prepare(contract, root)
        engine = Path(engine_root).resolve()
        verify_engine(engine)
        exported = _export(prepared, Path(repo_root).absolute())
        paths = prepared['paths'] + [exported]
        before = [_hash(p) for p in paths]
        result.update(zip(('contract_sha256', 'target_sha256', 'tests_sha256_raw', 'export_sha256'), before))
        result.update(tests_sha256_lf=prepared['tests_sha256_lf'],
                      effective_budget=prepared['metadata']['budget'],
                      test_cwd=prepared['metadata']['test_cwd'])
        worker = Path(__file__).with_name('native_level2_worker.py').resolve()
        # Preserve venv symlinks: resolving bin/python can select the base interpreter.
        command = [str(Path(python or sys.executable).absolute()), '-I', str(worker), str(engine), str(exported)]
        outcome = _invoke(command, timeout, root)
        verify_engine(engine)
        if before != [_hash(p) for p in paths]:
            result.update(verdict='INVALID', stage='inputs-changed')
        else:
            result.update(ok=outcome['verdict'] == 'PASS', verdict=outcome['verdict'],
                          stage=outcome.get('stage', 'engine'), gate=outcome)
    except TimeoutError:
        result.update(verdict='TIMEOUT', stage='execution')
    except ValueError as exc:
        result.update(verdict='INVALID', detail=str(exc))
    except (OSError, subprocess.SubprocessError):
        result.update(verdict='ERROR', detail='Runtime unavailable or execution error')
    finally:
        if exported is not None:
            try:
                exported.unlink(missing_ok=True)
            except OSError:
                result.update(ok=False, verdict='ERROR', stage='cleanup')
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('contract', type=Path)
    parser.add_argument('--repo-root', type=Path, default=Path.cwd())
    parser.add_argument('--engine-root', type=Path, required=True)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    result = run_level2(args.contract, args.repo_root, args.engine_root, python=args.python, timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['ok'] else (1 if result['verdict'] == 'FAIL' else 2)


if __name__ == '__main__':
    raise SystemExit(main())
