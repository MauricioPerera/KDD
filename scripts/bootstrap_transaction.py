"""Confine a declared file plan and recover ordinary IO failures.

This is not a sandbox for callbacks or protection against concurrent writers.
See knowledge/bootstrap-safety.md for the approved boundary and limits.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import errno
import os
from pathlib import Path
import stat
import tempfile


_ACTIVE = ContextVar('kdd_bootstrap_transaction', default=None)


def _invalid(path, reason):
    raise ValueError('BOOTSTRAP_PATH: {}: {}'.format(path, reason))


def _relative(path):
    relative = Path(path)
    if relative.is_absolute() or relative.drive or '..' in relative.parts or not relative.parts:
        _invalid(path, 'expected an exact relative file path')
    return relative


def _component(path, info, final):
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        _invalid(path, 'symlinks and reparse points are not managed files')
    if not final:
        if not stat.S_ISDIR(info.st_mode):
            _invalid(path, 'ancestor must be a directory')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        _invalid(path, 'destination must be a regular file with one hardlink')


def _checked(root, relative):
    path = root
    for index, part in enumerate(relative.parts):
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            return None
        _component(path, info, index == len(relative.parts) - 1)
    return info


def _preimage(path, info):
    if info is None:
        return None
    return (path.read_bytes(), stat.S_IMODE(info.st_mode), info.st_atime_ns, info.st_mtime_ns)


def _same(path, info, original):
    if info is None or original is None:
        return info is None and original is None
    raw, mode, _, modified = original
    return (stat.S_IMODE(info.st_mode) == mode and info.st_mtime_ns == modified
            and path.read_bytes() == raw)


def _restore(path, original):
    if original is None:
        path.unlink(missing_ok=True)
        return
    raw, mode, accessed, modified = original
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix='.kdd-restore-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(raw)
        os.utime(temporary, ns=(accessed, modified))
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _remove_empty(path):
    try:
        path.rmdir()
    except FileNotFoundError:
        pass
    except OSError as error:
        if error.errno not in (errno.ENOTEMPTY, errno.EEXIST):
            raise


class _Transaction:
    def __init__(self, root):
        self.root = root
        self.preimages = {}
        self.new_directories = set()

    def register(self, paths):
        relatives = list(dict.fromkeys(_relative(p) for p in paths))
        checked = {rel: _checked(self.root, rel) for rel in relatives}
        for relative, info in checked.items():
            if relative in self.preimages:
                continue
            path = self.root / relative
            self.preimages[relative] = _preimage(path, info)
            for parent in path.parents:
                if parent == self.root:
                    break
                if not parent.exists():
                    self.new_directories.add(parent)

    def rollback(self):
        errors = []
        for relative, original in reversed(list(self.preimages.items())):
            try:
                path = self.root / relative
                info = _checked(self.root, relative)
                if not _same(path, info, original):
                    _restore(path, original)
            except (OSError, ValueError) as error:
                errors.append(str(error))
        for path in sorted(self.new_directories, key=lambda p: len(p.parts), reverse=True):
            try:
                _remove_empty(path)
            except OSError as error:
                errors.append(str(error))
        if errors:
            raise OSError('BOOTSTRAP_ROLLBACK: ' + '; '.join(errors))


@contextmanager
def filesystem_transaction(repo_dir, paths):
    """Validate and recover only the caller's exact managed paths."""
    root = Path(repo_dir).resolve()
    if not root.is_dir():
        _invalid(repo_dir, 'project root must be an existing directory')
    transaction = _ACTIVE.get()
    if transaction is not None:
        if transaction.root != root:
            _invalid(repo_dir, 'nested transaction must use the same physical root')
        transaction.register(paths)
        yield
        return
    transaction = _Transaction(root)
    transaction.register(paths)
    token = _ACTIVE.set(transaction)
    try:
        yield
    except Exception:
        transaction.rollback()
        raise
    finally:
        _ACTIVE.reset(token)
