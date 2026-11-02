"""Exact oracle paths, read from approved contracts rather than candidates.

Inventory completeness is reviewed, not inferred from static imports. The
legacy fallback protects only the primary oracle; it is not acceptance.
"""
from pathlib import PurePosixPath


def approved_binary_paths(git, commit, files):
    """Read binary declarations from approved attributes, never candidate ones."""
    fields = git('check-attr', '--source=' + commit, '-z', 'text', '--', *files).split(b'\0')
    return {fields[index].decode('utf-8') for index in range(0, len(fields) - 1, 3)
            if fields[index + 2] == b'unset'}


def oracle_equal(current, approved, binary=False):
    """Canonical text permits checkout CRLF; binary bytes remain exact."""
    if binary or b'\0' in current or b'\0' in approved:
        return current == approved
    normalize = lambda data: data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return normalize(current) == normalize(approved)


def exact_path(value):
    """Reject ambiguous paths consistently on Unix and Windows."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError('Invalid oracle inventory path: ' + repr(value))
    if any(char in value for char in '\\\x00:*?[]'):
        raise ValueError('Invalid oracle inventory path: ' + repr(value))
    if PurePosixPath(value).is_absolute() or any(
            part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Oracle inventory path escapes or is ambiguous: ' + value)
    return value


def inventory_paths(metadata, required=False):
    """Return a sorted exact inventory; require explicit migration on demand."""
    if not isinstance(metadata, dict):
        raise ValueError('Approved contract must declare an oracle inventory')
    oracle = exact_path(metadata.get('tests'))
    if 'oracle_files' not in metadata:
        if required:
            raise ValueError('Explicit oracle inventory is required for acceptance')
        return [oracle]
    files = metadata['oracle_files']
    if not isinstance(files, list) or not files:
        raise ValueError('Oracle inventory must be a nonempty list')
    files = [exact_path(name) for name in files]
    if len({name.casefold() for name in files}) != len(files):
        raise ValueError('Oracle inventory has duplicate paths')
    if oracle not in files:
        raise ValueError('Oracle inventory must include tests')
    return sorted(files)


def local_file(root, name):
    """Resolve without accepting symlink components or repository escapes."""
    path = root
    for part in exact_path(name).split('/'):
        path = path / part
        if path.is_symlink():
            raise ValueError('Oracle inventory contains symlink: ' + name)
    if not path.resolve().is_relative_to(root):
        raise ValueError('Oracle inventory path escapes repository: ' + name)
    return path
