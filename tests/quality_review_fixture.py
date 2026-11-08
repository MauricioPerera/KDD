"""Small real Git projects for approved-object and manifest integration tests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from tests.test_fixture_preparation import configure_git

ROOT = Path(__file__).resolve().parents[1]


def fixture_environment():
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(PYTHONUTF8='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
               GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    return env


def run_git(root, *args, data=None):
    result = subprocess.run(['git', '-C', str(root), *args], input=data,
        capture_output=True, timeout=30, env=fixture_environment())
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
    return result.stdout


def prepare_identity(root):
    configure_git(root, {'user.name': 'Quality Integration',
        'user.email': 'quality@example.invalid', 'core.autocrlf': 'false',
        'commit.gpgsign': 'false'}, ephemeral=True)


class QualityReviewFixture:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.seed_owner = tempfile.TemporaryDirectory(prefix='kdd-quality-reviewed-seed-')
        cls.addClassCleanup(cls.seed_owner.cleanup)
        cls.seed = Path(cls.seed_owner.name) / 'seed'
        cls.seed.mkdir()
        run_git(cls.seed, 'init', '-q', '-b', 'main')
        prepare_identity(cls.seed)
        (cls.seed / 'scripts').mkdir()
        (cls.seed / 'scripts/process_tree.py').write_bytes((ROOT / 'scripts/process_tree.py').read_bytes())
        (cls.seed / 'product.txt').write_bytes(b'GOOD\n')
        (cls.seed / 'functional.py').write_bytes(
            b"from pathlib import Path\nassert Path('product.txt').read_bytes() == b'GOOD\\n'\n")
        (cls.seed / 'adversarial.py').write_bytes(
            b"from pathlib import Path\nvalue = Path('product.txt').read_bytes()\nassert value not in (b'BAD\\n', b'', b'UNREVIEWED')\n")
        (cls.seed / 'data.bin').write_bytes(b'\x00\nDATA')
        policy = {'protected': ['functional.py', 'adversarial.py', 'data.bin', 'scripts/process_tree.py'],
            'implementation': ['product.txt'], 'pm': [],
            'required_kinds': ['functional', 'adversarial'],
            'checks': [{'name': kind, 'kind': kind,
                'argv': [sys.executable, '-X', 'utf8', kind + '.py'], 'timeout': 20}
                for kind in ('functional', 'adversarial')]}
        (cls.seed / 'quality.json').write_bytes((json.dumps(policy, indent=2) + '\n').encode())
        run_git(cls.seed, 'add', '-A')
        run_git(cls.seed, 'commit', '-qm', 'reviewed project and real oracles')
        cls.originals = {name: (cls.seed / name).read_bytes()
            for name in policy['protected'] + ['quality.json']}

    def setUp(self):
        super().setUp()
        self.owner = tempfile.TemporaryDirectory(prefix='kdd-quality-object-case-')
        self.addCleanup(self.owner.cleanup)
        self.area = Path(self.owner.name).resolve()
        self.root = self.area / 'project'
        subprocess.run(['git', 'clone', '--quiet', '--shared', '-c', 'core.autocrlf=false',
            str(self.seed), str(self.root)], capture_output=True, check=True,
            timeout=30, env=fixture_environment())
        prepare_identity(self.root)
        self.approved = self.git('rev-parse', 'HEAD')

    def git(self, *args, data=None):
        return run_git(self.root, *args, data=data).decode('utf-8').strip()

    def commit(self, message='candidate'):
        self.git('add', '-A')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def cli(self, script='verify_quality.py', *, reference=None, extra_env=None):
        env = fixture_environment()
        env.update(extra_env or {})
        return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / script),
            '--repo-root', str(self.root), '--policy', 'quality.json', '--approved-ref', reference or self.approved],
            capture_output=True, encoding='utf-8', timeout=60, env=env)

    def weaken(self):
        for name in ('functional.py', 'adversarial.py'):
            (self.root / name).write_bytes(b"print('UNREVIEWED_ORACLE')\n")
        (self.root / 'product.txt').write_bytes(b'BAD\n')
        return self.commit('unreviewed oracle and defective product')

    def snapshot(self):
        files = {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.root.rglob('*') if path.is_file()
            and '.git' not in path.relative_to(self.root).parts}
        return {'files': files, 'head': self.git('rev-parse', 'HEAD'),
            'refs': self.git('for-each-ref', '--format=%(refname) %(objectname)'),
            'index': (self.root / '.git/index').read_bytes(),
            'config': (self.root / '.git/config').read_bytes()}
