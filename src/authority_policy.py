"""Closed policy schema; no best-effort interpretation of unsupported powers."""
from dataclasses import dataclass
import os


COMMANDS = ('sha256', 'validate_json')
DEVICES = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{i}' for p in ('COM', 'LPT') for i in range(1, 10)}


def valid_path(value):
    if not isinstance(value, str) or not value:
        return False
    if any(ord(c) < 32 or c in '\\:*?"<>|' for c in value):
        return False
    for segment in value.split('/'):
        if not segment or segment in ('.', '..') or segment.endswith(('.', ' ')):
            return False
        if segment.split('.')[0].upper() in DEVICES:
            return False
    return True


def _pattern(value):
    if value == '**':
        return True
    if not isinstance(value, str):
        return False
    prefix = value[:-3] if value.endswith('/**') else value
    return valid_path(prefix) and not any(c in prefix for c in '[]')


def _list(value, checker):
    return (isinstance(value, list) and all(checker(v) for v in value)
            and len(set(value)) == len(value))


def _positive(value):
    return type(value) is int and value > 0


def _fold(value):
    return value.casefold() if os.name == 'nt' else value


def covers(parent, child):
    """Exact paths / prefix/** / ** have a decidable subset relation."""
    parent, child = _fold(parent), _fold(child)
    if parent == '**' or parent == child:
        return True
    return parent.endswith('/**') and child.startswith(parent[:-2])


def matches(patterns, path):
    return any(covers(pattern, path) for pattern in patterns)


@dataclass(frozen=True)
class Policy:
    read: tuple
    write: tuple
    execute: tuple
    touch_only: tuple
    protected_paths: tuple
    max_operations: int
    max_bytes: int


def parse_policy(value):
    fields = {'version', 'authority', 'touch_only', 'protected_paths', 'limits'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Invalid policy fields')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported policy version')
    authority, limits = value['authority'], value['limits']
    if not isinstance(authority, dict) or set(authority) != {'read', 'write', 'execute'}:
        raise ValueError('Unsupported authority')
    if not isinstance(limits, dict) or set(limits) != {'max_operations', 'max_bytes'}:
        raise ValueError('Unsupported limits')
    patterns = (authority['read'], authority['write'], value['touch_only'], value['protected_paths'])
    if not all(_list(p, _pattern) for p in patterns):
        raise ValueError('Unsupported path patterns')
    if not _list(authority['execute'], lambda c: isinstance(c, str) and c in COMMANDS):
        raise ValueError('Unsupported command')
    if not all(_positive(limits[k]) for k in limits):
        raise ValueError('Invalid limits')
    return Policy(tuple(authority['read']), tuple(authority['write']), tuple(authority['execute']),
                  tuple(value['touch_only']), tuple(value['protected_paths']),
                  limits['max_operations'], limits['max_bytes'])


def allows_child(parent, child):
    for name in ('read', 'write', 'touch_only'):
        if not all(matches(getattr(parent, name), p) for p in getattr(child, name)):
            return False
    return (set(child.execute).issubset(parent.execute)
            and child.max_operations <= parent.max_operations
            and child.max_bytes <= parent.max_bytes)
