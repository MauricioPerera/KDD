"""Validate every workflow with a checksum-pinned, local actionlint binary."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

if __package__:
    from .process_tree import run
else:
    from process_tree import run

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'tools/workflow-syntax/actionlint.json'
LIMIT = 64 * 1024 * 1024


class WorkflowError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def fail(message, code='WORKFLOW_SYNTAX_TOOL'):
    raise WorkflowError(code, message)


def selected_tool():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    systems = {'win32': 'windows', 'linux': 'linux', 'darwin': 'darwin'}
    arches = {'amd64': 'amd64', 'x86_64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}
    system, arch = systems.get(sys.platform), arches.get(platform.machine().lower())
    if not system or not arch:
        fail('Unsupported actionlint platform')
    key = system + '_' + arch
    if data.get('schema_version') != 1 or data.get('version') != '1.7.12':
        fail('Unrecognized reviewed actionlint manifest')
    pin = data['platforms'][key]
    expected = 'actionlint_1.7.12_' + key + ('.zip' if system == 'windows' else '.tar.gz')
    if (pin['archive'] != expected or pin['url'] != 'https://github.com/rhysd/actionlint/releases/download/v1.7.12/' + expected
            or pin['executable'] != ('actionlint.exe' if system == 'windows' else 'actionlint')):
        fail('Invalid reviewed actionlint asset')
    for field in ('archive_sha256', 'binary_sha256'):
        if not isinstance(pin[field], str) or not re.fullmatch(r'[0-9a-f]{64}', pin[field]):
            fail('Invalid reviewed actionlint hash')
    return key, pin


def default_cache():
    return Path(tempfile.gettempdir()) / 'kdd-actionlint'


def external(path):
    raw = Path(path)
    if raw.is_symlink():
        fail('External destination must not be a symlink')
    resolved = raw.resolve()
    if resolved.is_relative_to(ROOT):
        fail('Tool cache and exports must be outside the tooling checkout')
    return resolved


def verified(path, digest):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        fail('Reviewed tool file missing or linked: ' + str(path))
    if path.stat().st_size > LIMIT:
        fail('Reviewed tool file exceeds size limit')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        fail('Reviewed tool hash mismatch: ' + str(path))
    return raw


def downloaded(pin):
    request = urllib.request.Request(pin['url'], headers={'User-Agent': 'KDD-workflow-syntax'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(LIMIT + 1)
    if len(raw) > LIMIT or hashlib.sha256(raw).hexdigest() != pin['archive_sha256']:
        fail('Downloaded actionlint archive hash or size mismatch')
    return raw


def executable_bytes(raw, pin):
    if pin['archive'].endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            member = archive.getinfo(pin['executable'])
            if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
                fail('Archive executable is not a regular file')
            binary = archive.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
            member = archive.getmember(pin['executable'])
            if not member.isfile():
                fail('Archive executable is not a regular file')
            binary = archive.extractfile(member).read()
    if len(binary) > LIMIT or hashlib.sha256(binary).hexdigest() != pin['binary_sha256']:
        fail('Extracted actionlint binary hash mismatch')
    return binary


def write_atomic(path, raw):
    if os.path.lexists(path):
        fail('Tool cache entry appeared during installation: ' + str(path))
    handle, name = tempfile.mkstemp(prefix='.actionlint-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install(cache_dir=None, archive=None):
    key, pin = selected_tool()
    cache = external(cache_dir or default_cache())
    directory = cache / '1.7.12' / key
    if (directory.is_symlink() or directory.parent.is_symlink()
            or not directory.resolve().is_relative_to(cache)):
        fail('Tool cache directory must not be linked')
    binary, package = directory / pin['executable'], directory / pin['archive']
    present = [os.path.lexists(binary), os.path.lexists(package)]
    if any(present) and not all(present):
        fail('Incomplete actionlint cache; remove it explicitly before installing')
    if not any(present):
        raw = verified(archive, pin['archive_sha256']) if archive else downloaded(pin)
        payload = executable_bytes(raw, pin)
        directory.mkdir(parents=True, exist_ok=True)
        write_atomic(package, raw)
        write_atomic(binary, payload)
        binary.chmod(0o755)
    verified(package, pin['archive_sha256'])
    verified(binary, pin['binary_sha256'])
    return dict(ok=True, code='WORKFLOW_SYNTAX_TOOL_READY', version='1.7.12',
                platform=key, binary=str(binary), archive=str(package), sha256=pin['binary_sha256'])


def export_tool(data, env_file, path_file):
    values = [data['binary'], data['archive']]
    if any('\n' in value or '\r' in value for value in values):
        fail('Newlines are forbidden in exported tool paths')
    env_path, path_path = external(env_file), external(path_file)
    if env_path == path_path:
        fail('GitHub env/path export destinations must differ')
    if any(p.exists() and not p.is_file() for p in (env_path, path_path)):
        fail('GitHub export destination must be a regular file')
    for path in (env_path, path_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    with env_path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('KDD_ACTIONLINT_BINARY=' + values[0] + '\nKDD_ACTIONLINT_ARCHIVE=' + values[1] + '\n')
    with path_path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(str(Path(values[0]).parent) + '\n')


def workflow_files(root):
    directory = root / '.github/workflows'
    if not directory.is_dir() or not directory.resolve().is_relative_to(root):
        fail('Missing or external .github/workflows directory', 'WORKFLOW_SYNTAX_INPUT')
    files = sorted((p for p in directory.iterdir() if p.suffix in ('.yml', '.yaml')),
                   key=lambda p: p.relative_to(root).as_posix())
    if not files:
        fail('Workflow inventory is empty', 'WORKFLOW_SYNTAX_INPUT')
    for path in files:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            fail('Workflow entry must be a regular internal file: ' + str(path), 'WORKFLOW_SYNTAX_INPUT')
    return files


def checked_binary(binary, key, pin):
    selected = (binary or os.environ.get('KDD_ACTIONLINT_BINARY') or shutil.which(pin['executable'])
                or str(default_cache() / '1.7.12' / key / pin['executable']))
    path = Path(selected)
    verified(path, pin['binary_sha256'])
    return path.resolve()


def validate_workflows(repo_root: str, binary: str | None = None) -> dict:
    root = Path(repo_root).resolve()
    files = workflow_files(root)
    key, pin = selected_tool()
    program = checked_binary(binary, key, pin)
    with tempfile.TemporaryDirectory(prefix='kdd-workflow-config-') as temporary:
        config = Path(temporary) / 'actionlint.yaml'
        config.write_text('{}\n', encoding='utf-8')
        process = run([str(program), '-shellcheck=', '-pyflakes=', '-config-file', str(config),
                       '-format', '{{json .}}', *map(str, files)], cwd=root, timeout=120,
                      capture_output=True, text=True, encoding='utf-8', errors='backslashreplace')
    try:
        diagnostics = json.loads(process.stdout)
    except ValueError as exc:
        fail('actionlint did not produce JSON: ' + str(exc))
    if not isinstance(diagnostics, list) or any(not isinstance(d, dict) for d in diagnostics):
        fail('actionlint diagnostic report is invalid')
    for diagnostic in diagnostics:
        if not all(field in diagnostic for field in ('filepath', 'line', 'column', 'kind', 'message')):
            fail('actionlint diagnostic fields are incomplete')
    if process.returncode not in (0, 1) or (process.returncode == 0) != (not diagnostics):
        fail('actionlint failed or returned inconsistent evidence: ' + (process.stderr or str(process.returncode)))
    return dict(ok=process.returncode == 0,
                code='WORKFLOW_SYNTAX_PASS' if process.returncode == 0 else 'WORKFLOW_SYNTAX',
                files=[p.relative_to(root).as_posix() for p in files], version='1.7.12',
                binary=str(program), diagnostics=diagnostics, tool_exit_code=process.returncode)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        fail(message, 'WORKFLOW_SYNTAX_INPUT')


def main(argv=None):
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('install')
    for name in ('cache-dir', 'archive', 'github-env', 'github-path'):
        setup.add_argument('--' + name)
    check = commands.add_parser('check')
    check.add_argument('--repo-root', required=True)
    check.add_argument('--actionlint')
    try:
        args = parser.parse_args(argv)
        if args.command == 'install':
            if bool(args.github_env) != bool(args.github_path):
                fail('GitHub env/path exports must be provided together')
            if args.github_env:
                external(args.github_env)
                external(args.github_path)
            data = install(args.cache_dir, args.archive)
            if args.github_env:
                export_tool(data, args.github_env, args.github_path)
        else:
            data = validate_workflows(args.repo_root, args.actionlint)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError,
            tarfile.TarError, zipfile.BadZipFile) as exc:
        data = dict(ok=False, code=getattr(exc, 'code', 'WORKFLOW_SYNTAX_TOOL'),
                    message=str(exc), files=[], diagnostics=[])
    print(json.dumps(data, ensure_ascii=True))
    return 0 if data['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
