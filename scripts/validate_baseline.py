"""Compare contract/oracle to an independently approved Git commit.

The caller must select the trusted reference, from outside implementer control.
This read-only check does not provide branch protection or a trusted runner.
"""
import argparse
from pathlib import Path
import subprocess
from validate_contracts import parse_frontmatter
from oracle_inventory import approved_binary_paths, inventory_paths, local_file, oracle_equal


def _git(root, *args):
    try:
        return subprocess.check_output(
            ['git', '-C', str(root), *args], stderr=subprocess.PIPE, timeout=30)
    except (subprocess.SubprocessError, OSError) as exc:
        raise ValueError('Cannot read approved Git reference or artifact') from exc


def _normalize(content):
    return content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _relative(root, file):
    try:
        path = Path(file)
        name = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
        if name != '.':
            local_file(root, name)
        return name
    except (ValueError, TypeError) as exc:
        raise ValueError('Artifact path escapes repository') from exc


def validate_baseline(contract, approved_ref, repo_root='.'):
    root = Path(repo_root).resolve()
    rel = _relative(root, contract)
    commit = _git(root, 'rev-parse', '--verify', '--end-of-options',
                  approved_ref + '^{commit}').decode().strip()
    approved_contract = _git(root, 'show', commit + ':' + rel)
    metadata, _ = parse_frontmatter(approved_contract.decode('utf-8'))
    if not isinstance(metadata, dict) or not metadata.get('tests'):
        raise ValueError('Approved contract must declare tests')
    findings = []
    artifacts = [(rel, approved_contract)]
    binary = (approved_binary_paths(lambda *args: _git(root, *args), commit, inventory_paths(metadata))
              if 'oracle_files' in metadata else set())
    for name in inventory_paths(metadata):
        entry = _git(root, 'ls-tree', commit, '--', name).decode().split()
        if not entry or entry[0] not in ('100644', '100755'):
            raise ValueError('Approved oracle inventory file missing or not regular: ' + name)
        artifacts.append((name, _git(root, 'show', commit + ':' + name)))
    for file, expected in artifacts:
        try:
            current = local_file(root, file).read_bytes()
        except (OSError, ValueError):
            findings.append(file + ': approved artifact missing')
            continue
        exact = file != rel and 'oracle_files' in metadata
        if (not oracle_equal(current, expected, file in binary) if exact else
                _normalize(current) != _normalize(expected)):
            findings.append(file + ': differs from approved reference ' + commit)
    return findings


_BATCH_BYTES = 8 * 1024 * 1024
_BATCH_COUNT = 32


def _batch_row(line):
    fields = line.split()
    if (len(fields) != 3 or len(fields[0]) not in (40, 64)
            or any(c not in b'0123456789abcdef' for c in fields[0])
            or not fields[2].isdigit()):
        raise ValueError('Cannot read approved Git reference or artifact')
    return fields[0], fields[1], int(fields[2])


def _cat_file(root, commit, names, mode):
    inputs = ''.join(commit + ':' + name + '\n' for name in names).encode('utf-8')
    try:
        proc = subprocess.run(['git', '-C', str(root), 'cat-file', mode],
                              input=inputs, capture_output=True, timeout=30)
    except (subprocess.SubprocessError, OSError) as exc:
        raise ValueError('Cannot read approved Git reference or artifact') from exc
    if proc.returncode:
        raise ValueError('Cannot read approved Git reference or artifact')
    return proc.stdout


def _batch_metadata(root, commit, names):
    lines = _cat_file(root, commit, names, '--batch-check').splitlines()
    if len(lines) != len(names):
        raise ValueError('Cannot read approved Git reference or artifact')
    return {name: _batch_row(line) for name, line in zip(names, lines)}


def _batch_result(data, names, metadata):
    result, offset = {}, 0
    for name in names:
        end = data.find(b'\n', offset)
        if end < 0:
            raise ValueError('Cannot read approved Git reference or artifact')
        row = _batch_row(data[offset:end])
        if row != metadata[name] or row[1] != b'blob':
            raise ValueError('Cannot read approved Git reference or artifact')
        start, stop = end + 1, end + 1 + row[2]
        if stop >= len(data) or data[stop:stop + 1] != b'\n':
            raise ValueError('Cannot read approved Git reference or artifact')
        result[name] = data[start:stop]
        offset = stop + 1
    if offset != len(data):
        raise ValueError('Cannot read approved Git reference or artifact')
    return result


def _batch_chunk(root, commit, names, metadata):
    return _batch_result(_cat_file(root, commit, names, '--batch'), names, metadata)


def _partition_blobs(root, commit, names, metadata):
    chunks, pending, size, result = [], [], 0, {}
    for name in names:
        _, kind, length = metadata[name]
        if kind != b'blob' or length > _BATCH_BYTES:
            result[name] = _git(root, 'show', commit + ':' + name)
            continue
        if pending and (len(pending) == _BATCH_COUNT or size + length > _BATCH_BYTES):
            chunks.append(pending)
            pending, size = [], 0
        pending.append(name)
        size += length
    if pending:
        chunks.append(pending)
    return chunks, result


def _approved_blobs(root, commit, names):
    unique = list(dict.fromkeys(names))
    result, regular = {}, []
    for name in unique:
        if '\n' in name or '\r' in name:
            result[name] = _git(root, 'show', commit + ':' + name)
        else:
            regular.append(name)
    if not regular:
        return result
    metadata = _batch_metadata(root, commit, regular)
    chunks, fallback = _partition_blobs(root, commit, regular, metadata)
    result.update(fallback)
    for chunk in chunks:
        result.update(_batch_chunk(root, commit, chunk, metadata))
    return result


def _approved_entries(root, commit, contracts, tree):
    paths = {contract: _relative(root, contract) for contract in contracts}
    contents = _approved_blobs(root, commit, list(paths.values()))
    entries = {}
    for contract in contracts:
        relative = paths[contract]
        approved = contents[relative]
        metadata, _ = parse_frontmatter(approved.decode('utf-8'))
        if not isinstance(metadata, dict) or not metadata.get('tests'):
            raise ValueError('Approved contract must declare tests')
        try:
            files = inventory_paths(metadata)
        except ValueError as exc:
            if 'oracle_files' not in metadata:
                raise ValueError('Artifact path escapes repository') from exc
            raise
        for name in files:
            if tree.get(name) not in ('100644', '100755'):
                raise ValueError('Approved oracle inventory file missing or not regular: ' + name)
        entries[contract] = (relative, approved, files, 'oracle_files' in metadata)
    names = list(dict.fromkeys(name for entry in entries.values() for name in entry[2]))
    binary_names = sorted({name for entry in entries.values() if entry[3] for name in entry[2]})
    binary = set()
    for offset in range(0, len(binary_names), _BATCH_COUNT):
        binary.update(approved_binary_paths(lambda *args: _git(root, *args), commit,
                                            binary_names[offset:offset + _BATCH_COUNT]))
    return entries, _approved_blobs(root, commit, names), binary


def _compare_approved(root, commit, artifacts):
    findings = []
    for file, expected, exact, binary in artifacts:
        try:
            current = local_file(root, file).read_bytes()
        except (OSError, ValueError):
            findings.append(file + ': approved artifact missing')
            continue
        if (not oracle_equal(current, expected, binary) if exact else
                _normalize(current) != _normalize(expected)):
            findings.append(file + ': differs from approved reference ' + commit)
    return findings


def _approved_tree(root, commit):
    result = {}
    raw = _git(root, 'ls-tree', '-r', '-z', '--full-tree', commit)
    for record in filter(None, raw.split(b'\0')):
        info, name = record.split(b'\t', 1)
        mode, kind, _oid = info.decode('ascii').split(' ')
        result[name.decode('utf-8', errors='surrogateescape')] = mode if kind == 'blob' else ''
    return result


def validate_all_baselines(approved_ref, repo_root='.', contracts_dir='knowledge/contracts'):
    """Check every current and approved contract, including additions/deletions."""
    root = Path(repo_root).resolve()
    directory = _relative(root, contracts_dir)
    commit = _git(root, 'rev-parse', '--verify', '--end-of-options',
                  approved_ref + '^{commit}').decode().strip()
    tree = _approved_tree(root, commit)
    prefix = '' if directory == '.' else directory.rstrip('/') + '/'
    approved = {p for p in tree if p.startswith(prefix)}
    approved = {p for p in approved if p.endswith('.md') and
                not Path(p).name.startswith('TEMPLATE-')}
    current_dir = root / directory
    if not current_dir.is_dir():
        raise ValueError('Contracts directory missing: ' + directory)
    current = {p.relative_to(root).as_posix() for p in current_dir.glob('*.md')
               if not p.name.startswith('TEMPLATE-')}
    if not approved and not current:
        raise ValueError('No contracts found in approved reference or current tree')
    entries, oracles, binary = _approved_entries(root, commit, sorted(approved & current), tree)
    findings = []
    for contract in sorted(approved | current):
        if contract not in approved:
            findings.append(contract + ': not in approved reference ' + commit)
        elif contract not in current:
            findings.append(contract + ': approved contract missing')
        else:
            relative, expected, files, exact = entries[contract]
            artifacts = [(relative, expected, False, False)]
            artifacts.extend((name, oracles[name], exact, name in binary) for name in files)
            findings.extend(_compare_approved(root, commit, artifacts))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('contract', nargs='?')
    parser.add_argument('--all', action='store_true', help='check all contracts')
    parser.add_argument('--contracts-dir', default='knowledge/contracts')
    parser.add_argument('--approved-ref', required=True)
    parser.add_argument('--repo-root', default='.')
    args = parser.parse_args()
    if args.all == bool(args.contract):
        parser.error('specify exactly one of CONTRACT or --all')
    try:
        if args.all:
            findings = validate_all_baselines(args.approved_ref, args.repo_root,
                                              args.contracts_dir)
        else:
            findings = validate_baseline(args.contract, args.approved_ref, args.repo_root)
    except (ValueError, UnicodeError) as exc:
        print('FAIL: ' + str(exc))
        return 2
    for finding in findings:
        print('FAIL: ' + finding)
    if not findings:
        print('PASS: contract and oracle match the approved reference')
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
