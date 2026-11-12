"""Measure the initialized Windows suite for the exact PR 187 merge tree."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


SOURCE_SHA = 'e7af3bffd3cb54db39974eff4b0bde0cfe3d7c60'
SOURCE_TREE = '8501f0a4655cf275afe61390dd663190523e212a'
CONTAINMENT_REF = '74d357f7099651b9b39dc8088f725183a672ec94'
EXPECTED_CASES = 2232
IDS_SHA256 = 'd9c8d67f52373d64f03ca7d002bf05bf46c3fb5deae1db1f3cfefdef8ffe12d8'
SKIPS_SHA256 = 'a9cfc6320f15e2b341af6aa483c5af9223b0c57e16f3291b5ba95f7255eb29ce'
TIMEOUT = 600
COLLECTOR = Path(__file__).resolve().parents[2] / 'scripts/postinit_timeout_observation.py'


def _git(source, *args):
    return subprocess.check_output(['git', '--no-replace-objects', '-C', str(source), *args], timeout=30)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _digest(ids):
    return hashlib.sha256(('\n'.join(sorted(ids)) + '\n').encode('utf-8')).hexdigest()


def _fixture(source):
    original_path = sys.path[:]
    sys.path.insert(0, str(source))
    try:
        return _load('measured_init_fixture', source / 'tests/test_init_project.py')
    finally:
        sys.path[:] = original_path


def _completed_profile(path):
    report = json.loads(path.read_bytes())
    if (not report['ok'] or report['workers'] != 10 or report['tests_run'] != EXPECTED_CASES
            or report['fixture_omitted_ids'] or _digest(report['expected_ids']) != IDS_SHA256
            or _digest(report['executed_ids']) != IDS_SHA256
            or _digest([item['id'] for item in report['skipped']]) != SKIPS_SHA256):
        raise ValueError('initialized suite differs from its reference inventory')
    modules = []
    for item in report['modules']:
        name = item['module']
        if not all(part.isidentifier() for part in name.split('.')):
            raise ValueError('invalid module name in final profile')
        modules.append(dict(name=name, cases=item['tests_run'], duration_seconds=item['duration_seconds']))
    return dict(cases=EXPECTED_CASES, ids_sha256=IDS_SHA256, skips_sha256=SKIPS_SHA256,
                modules=modules)


def _partial_profile(area, project):
    try:
        result = subprocess.run([sys.executable, '-I', str(COLLECTOR), '--temp-root', str(area),
                                 '--project-root', str(project)], capture_output=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return dict(state='inconclusive', modules=[])


def measure(source, area):
    containment = area / 'process_tree.py'
    containment.write_bytes(_git(source, 'show', CONTAINMENT_REF + ':scripts/process_tree.py'))
    run = _load('reviewed_probe_process_tree', containment).run
    fixture = _fixture(source)
    project = Path(tempfile.mkdtemp(dir=area))
    fixture._copy_repo(project, full=True)
    initialized = fixture._run_cli(str(project), '--apply')
    if initialized.returncode or (project / '.git').exists():
        raise ValueError('the measured fixture could not initialize its private copy')
    (project / 'tests/test_init_project.py').unlink()
    report = area / 'final.json'
    argv = [sys.executable, str(project / 'scripts/init_post_apply_suite.py'),
            '--repo-root', str(project), '--report-json', str(report)]
    env = dict(os.environ, TEMP=str(area), TMP=str(area), TMPDIR=str(area))
    started = time.perf_counter()
    try:
        result = run(argv, cwd=project, env=env, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - started
        return dict(status='timeout', duration_seconds=elapsed, observation=_partial_profile(area, project)), 124
    elapsed = time.perf_counter() - started
    if result.returncode:
        return dict(status='failed', duration_seconds=elapsed), result.returncode
    return dict(status='completed', duration_seconds=elapsed, profile=_completed_profile(report)), 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    source = args.source.resolve(strict=True)
    temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    output = args.out.resolve()
    control = COLLECTOR.parent.parent
    if os.name != 'nt' or output.parent != temp or temp.is_relative_to(source) or temp.is_relative_to(control):
        raise SystemExit('This probe requires Windows and external runner storage')
    if (_git(source, 'rev-parse', 'HEAD', 'HEAD^{tree}').decode('ascii').splitlines()
            != [SOURCE_SHA, SOURCE_TREE] or _git(source, 'status', '--porcelain')):
        raise SystemExit('Measured checkout differs from the exact reviewed PR tree')
    output.mkdir()
    with tempfile.TemporaryDirectory(prefix='kdd-probe-', dir=temp) as work:
        measurement, exit_code = measure(source, Path(work))
    summary = dict(source_sha=SOURCE_SHA, source_tree=SOURCE_TREE, containment_ref=CONTAINMENT_REF,
                   run_id=os.environ.get('GITHUB_RUN_ID'), run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT'),
                   workers=10, timeout_seconds=TIMEOUT, exit_code=exit_code, **measurement)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f"Initialized Windows suite {measurement['status']} in {measurement['duration_seconds']:.2f} s")
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
