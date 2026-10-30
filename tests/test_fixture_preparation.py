"""Real native aliases and local Git settings for bounded fixture preparation."""
import ctypes
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
from typing import NamedTuple
import unittest


class NativeResult(NamedTuple):
    """Normalized native-operation status, not a fabricated subprocess result."""
    returncode: int = 0
    stdout: str = ''
    stderr: str = ''


def _junction(link, target):
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    substitute = ('\\??\\' + str(target)).encode('utf-16-le')
    printable = str(target).encode('utf-16-le')
    names = substitute + b'\0\0' + printable + b'\0\0'
    raw = struct.pack('<IHHHHHH', 0xA0000003, len(names) + 8, 0,
                      0, len(substitute), len(substitute) + 2, len(printable)) + names
    link.mkdir()
    handle = kernel.CreateFileW('\\\\?\\' + str(link), 0x40000000, 7, None, 3, 0x02200000, None)
    try:
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(raw)
        returned = wintypes.DWORD()
        if not kernel.DeviceIoControl(handle, 0x900A4, buffer, len(raw), None, 0, ctypes.byref(returned), None):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        if handle != ctypes.c_void_p(-1).value:
            kernel.CloseHandle(handle)
            handle = ctypes.c_void_p(-1).value
        link.rmdir()
        raise
    finally:
        if handle != ctypes.c_void_p(-1).value:
            kernel.CloseHandle(handle)


def directory_alias(link, target, owner):
    owner = Path(owner).resolve(strict=True)
    link, target = Path(link).absolute(), Path(target).resolve(strict=True)
    if (not owner.is_dir() or not target.is_dir() or not target.is_relative_to(owner)
            or not link.parent.resolve(strict=True).is_relative_to(owner)):
        raise ValueError('Fixture alias must stay within its owned directory')
    try:
        link.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError('Fixture alias destination already exists')
    if os.name == 'nt':
        _junction(link, target)
    else:
        link.symlink_to(target, target_is_directory=True)
    if link.resolve(strict=True) != target:
        raise OSError('Native fixture alias does not resolve to its target')
    return NativeResult()


def configure_git(root, values, *, ephemeral=False):
    """Prepare only the constant local settings of a fresh owned Git fixture."""
    if type(ephemeral) is not bool:
        raise ValueError('Fixture ephemeral mode must be a boolean')
    allowed = {'user.name', 'user.email', 'maintenance.autoDetach', 'gc.autoDetach',
               'core.autocrlf', 'commit.gpgsign'}
    if not isinstance(values, dict) or not values or set(values) - allowed:
        raise ValueError('Unsupported fixture Git setting')
    for key, value in values.items():
        if (not isinstance(value, str) or not value or any(ord(c) < 32 for c in value)
                or (not key.startswith('user.') and value != 'false')):
            raise ValueError('Invalid fixture Git setting value')
    root = Path(root).resolve(strict=True)
    gitdir, config = root / '.git', root / '.git/config'
    for path in (gitdir, config):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Fixture Git metadata must be local regular storage')
    info = config.stat()
    if not gitdir.is_dir() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Fixture config must be a regular file with one link')
    suffix = ''
    for key, value in values.items():
        section, name = key.split('.')
        suffix += '\n[{}]\n\t{} = {}\n'.format(section, name, json.dumps(value, ensure_ascii=False))
    if ephemeral:
        suffix += '\n[maintenance]\n\tauto = false\n[gc]\n\tauto = 0\n'
    original = config.read_bytes()
    fd, temporary = tempfile.mkstemp(prefix='kdd-fixture-config-', dir=gitdir)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(original + suffix.encode('utf-8'))
        temporary.chmod(stat.S_IMODE(info.st_mode))
        os.replace(temporary, config)
    finally:
        temporary.unlink(missing_ok=True)


_PROBE = r'''import json,os,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
owner=Path(sys.argv[2]);kind=sys.argv[3];project=owner/'project';project.mkdir()
events=[]
sys.addaudithook(lambda event,args: events.append(event) if event=='subprocess.Popen' else None)
if kind=='bootstrap':
    from tests.test_bootstrap_boundary import SandboxFixture
    target=owner/'target';target.mkdir();(target/'marker').write_text('canary')
    link=project/'alias';case=SandboxFixture();case.area=owner;case.root=project;case.env=dict(os.environ)
    case.directory_alias(link,target)
elif kind=='history':
    from tests.test_task_committed_artifacts import TaskCommittedArtifactsTests
    link=project/'src';link.mkdir();(link/'marker').write_text('canary')
    method=next(n for n in dir(TaskCommittedArtifactsTests) if n.startswith('test_'))
    case=TaskCommittedArtifactsTests(method);case.root=project;case.temp=SimpleNamespace(name=str(owner))
    target=case.alias('src')
else:
    from tests.test_task_git import Repository
    from tests.test_generated_task_evidence import TaskProject
    if kind=='repository':
        case=Repository();project=case.root
    else:case=TaskProject(project,count=1)
    print(json.dumps({'processes':len(events)}));raise SystemExit(0)
info=link.lstat()
print(json.dumps({'processes':len(events),'target':str(target.resolve()),'actual':str(link.resolve()),
    'reparse':bool(getattr(info,'st_file_attributes',0)&0x400),'symlink':link.is_symlink(),
    'canary':(target/'marker').read_text()}))
if link.is_symlink():link.unlink()
else:link.rmdir()
'''


class FixturePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd fixture \u00f1 & ')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.owner = self.area / 'owner';self.owner.mkdir()
        self.target = self.owner / 'target \u00f1 &';self.target.mkdir()
        (self.target / 'canary').write_bytes(b'unchanged')
        self.link = self.owner / 'alias \u00f1 &'

    def create(self):
        result = directory_alias(self.link, self.target, self.owner)
        self.assertEqual(result.returncode, 0)
        self.addCleanup(self.remove_alias, self.link)
        return self.link.lstat()

    @staticmethod
    def remove_alias(path):
        if path.is_symlink():path.unlink()
        elif path.exists():path.rmdir()

    def test_creates_real_native_alias_and_preserves_canary(self):
        info = self.create()
        self.assertEqual(self.link.resolve(), self.target.resolve())
        self.assertEqual((self.link/'canary').read_bytes(), b'unchanged')
        if os.name == 'nt':
            self.assertTrue(info.st_file_attributes & 0x400)
            self.assertEqual(info.st_reparse_tag, 0xA0000003)
        else:self.assertTrue(stat.S_ISLNK(info.st_mode))

    def test_existing_file_is_never_replaced(self):
        self.link.write_bytes(b'existing')
        with self.assertRaises(ValueError):directory_alias(self.link,self.target,self.owner)
        self.assertEqual(self.link.read_bytes(),b'existing')

    def test_existing_directory_is_never_replaced(self):
        self.link.mkdir();(self.link/'marker').write_bytes(b'existing')
        with self.assertRaises(ValueError):directory_alias(self.link,self.target,self.owner)
        self.assertEqual((self.link/'marker').read_bytes(),b'existing')

    def test_external_target_rejected_without_writing(self):
        outside=self.area/'external';outside.mkdir()
        with self.assertRaises(ValueError):directory_alias(self.link,outside,self.owner)
        self.assertFalse(self.link.exists())

    def test_external_parent_rejected_without_writing(self):
        outside=self.area/'outside-link'
        with self.assertRaises(ValueError):directory_alias(outside,self.target,self.owner)
        self.assertFalse(outside.exists())

    def test_missing_target_rejected_without_writing(self):
        with self.assertRaises((ValueError,FileNotFoundError)):
            directory_alias(self.link,self.owner/'absent',self.owner)
        self.assertFalse(self.link.exists())

    def test_owner_must_be_directory(self):
        owner=self.area/'file';owner.write_bytes(b'owner')
        with self.assertRaises(ValueError):directory_alias(self.link,self.target,owner)
        self.assertEqual(owner.read_bytes(),b'owner')

    def repository(self):
        env=dict(os.environ,GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1')
        subprocess.run(['git','init','-q','-b','main',str(self.owner)],check=True,env=env,capture_output=True)
        return env

    def test_git_reads_local_settings_and_performs_real_commit(self):
        env=self.repository()
        values={'user.name':'Fixture "Ni\u00f1o" \\ team','user.email':'fixture@example.invalid',
            'maintenance.autoDetach':'false','gc.autoDetach':'false','core.autocrlf':'false','commit.gpgsign':'false'}
        configure_git(self.owner,values)
        output=subprocess.check_output(['git','-C',str(self.owner),'config','--local','--null','--list'],env=env).decode('utf-8')
        actual=dict(item.split('\n',1) for item in output.split('\0') if item)
        for key,value in values.items():self.assertEqual(actual[key.lower()],value)
        subprocess.run(['git','-C',str(self.owner),'add','-A'],env=env,check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.owner),'commit','-qm','Real fixture commit'],env=env,check=True,capture_output=True)
        author=subprocess.check_output(['git','-C',str(self.owner),'show','-s','--format=%an'],env=env).decode('utf-8').strip()
        self.assertEqual(author,values['user.name'])

    def test_invalid_configuration_preserves_file_and_index(self):
        self.repository();config=self.owner/'.git/config';before=config.read_bytes()
        for values in [{'include.path':'external'},{'user.name':'line\nbreak'},{'gc.autoDetach':'true'},
                       {'maintenance.auto':'false'},{'gc.auto':'0'},{'user.email':''}]:
            with self.subTest(values=values),self.assertRaises(ValueError):configure_git(self.owner,values)
            self.assertEqual(config.read_bytes(),before)
        self.assertFalse((self.owner/'.git/index').exists())

    def test_hardlinked_config_preserves_canary(self):
        self.repository();config=self.owner/'.git/config';outside=self.area/'config-canary'
        os.link(config,outside);before=outside.read_bytes()
        with self.assertRaises(ValueError):configure_git(self.owner,{'user.name':'fixture'})
        self.assertEqual(outside.read_bytes(),before)

    def probe(self,kind):
        owner=self.owner/kind;owner.mkdir()
        root=Path(__file__).resolve().parents[1]
        env=dict(os.environ,PYTHONUTF8='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1')
        result=subprocess.run([sys.executable,'-X','utf8','-c',_PROBE,str(root),str(owner),kind],
            capture_output=True,text=True,encoding='utf-8',env=env,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_bootstrap_fixture_creates_native_object_without_process(self):
        result=self.probe('bootstrap')
        self.assertEqual(result['actual'],result['target']);self.assertEqual(result['canary'],'canary')
        self.assertEqual(result['processes'],0,'fixture must not start PowerShell or another helper process')

    def test_history_fixture_creates_native_object_without_process(self):
        result=self.probe('history')
        self.assertEqual(result['actual'],result['target']);self.assertEqual(result['canary'],'canary')
        self.assertEqual(result['processes'],0,'fixture must not start PowerShell or another helper process')

    def test_repository_fixture_has_only_real_init_add_commit_and_head_processes(self):
        self.assertEqual(self.probe('repository')['processes'],4)

    def test_product_fixture_has_only_real_init_add_commit_and_head_processes(self):
        self.assertEqual(self.probe('product')['processes'],4)
