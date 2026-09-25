"""Compare contract/oracle to an independently approved Git commit.

The caller must select the trusted reference, from outside implementer control.
This read-only check does not provide branch protection or a trusted runner.
"""
import argparse
from pathlib import Path
import subprocess
from validate_contracts import parse_frontmatter


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
        return (root / file).resolve().relative_to(root).as_posix()
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
    oracle = _relative(root, metadata['tests'])
    findings = []
    for file, expected in [(rel, approved_contract),
                           (oracle, _git(root, 'show', commit + ':' + oracle))]:
        try:
            current = (root / file).read_bytes()
        except OSError:
            findings.append(file + ': approved artifact missing')
            continue
        if _normalize(current) != _normalize(expected):
            findings.append(file + ': differs from approved reference ' + commit)
    return findings


def validate_all_baselines(approved_ref, repo_root='.', contracts_dir='knowledge/contracts'):
    """Check every current and approved contract, including additions/deletions."""
    root = Path(repo_root).resolve()
    directory = _relative(root, contracts_dir)
    commit = _git(root, 'rev-parse', '--verify', '--end-of-options',
                  approved_ref + '^{commit}').decode().strip()
    approved = set(_git(root, 'ls-tree', '-r', '--name-only', commit, '--',
                        directory).decode('utf-8').splitlines())
    approved = {p for p in approved if p.endswith('.md') and
                not Path(p).name.startswith('TEMPLATE-')}
    current_dir = root / directory
    if not current_dir.is_dir():
        raise ValueError('Contracts directory missing: ' + directory)
    current = {p.relative_to(root).as_posix() for p in current_dir.glob('*.md')
               if not p.name.startswith('TEMPLATE-')}
    if not approved and not current:
        raise ValueError('No contracts found in approved reference or current tree')
    findings = []
    for contract in sorted(approved | current):
        if contract not in approved:
            findings.append(contract + ': not in approved reference ' + commit)
        elif contract not in current:
            findings.append(contract + ': approved contract missing')
        else:
            findings.extend(validate_baseline(contract, commit, root))
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
