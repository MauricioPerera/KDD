#!/usr/bin/env python3
"""Verify that project closure cites an earlier successful CI run."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib import request

from validate_completion import _CHECKBOX, _ID, _criteria, _load_policy, validate_completion


_SHA = re.compile(r'[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?')
_REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
_SPEC = r'(CONTRACT-[0-9]+)-[^/]+\.md'
_REPORT = re.compile(r'docs/reports/(CONTRACT-[0-9]+)-(?:REPORT\.md|EVIDENCE\.json)')
_GIT_ERRORS = (OSError, ValueError, subprocess.TimeoutExpired)


def _finding(rule, message):
    return {'rule': rule, 'msg': message}


def verify_closure_diff(changed_paths, specs_dir='specs'):
    """Reject code or oracle changes after the run that was cited."""
    findings = []
    for path in changed_paths:
        allowed = (path == 'CHANGELOG.md' or _spec_prefix(path, specs_dir)
                   or _REPORT.fullmatch(path))
        if not allowed:
            findings.append(_finding('CI_SOURCE_DRIFT',
                                     'changed after cited CI run: ' + path))
    return findings


def _run_reference(evidence, repository):
    ci = evidence.get('ci') if isinstance(evidence, dict) else None
    ci = ci if isinstance(ci, dict) else {}
    url, sha = ci.get('run_url'), ci.get('head_sha')
    pattern = r'https://github\.com/{}/actions/runs/([0-9]+)'.format(
        re.escape(repository))
    match = re.fullmatch(pattern, url) if isinstance(url, str) else None
    if not match or not isinstance(sha, str) or not _SHA.fullmatch(sha):
        return None
    return int(match.group(1)), url, sha


def _run_identity_findings(run, repository, run_id, url, sha):
    findings = []
    if run.get('head_sha') != sha:
        findings.append(_finding('CI_RUN_SHA', 'run head SHA differs from evidence'))
    remote_repo = run.get('repository')
    remote_repo = remote_repo if isinstance(remote_repo, dict) else {}
    if remote_repo.get('full_name') != repository:
        findings.append(_finding('CI_RUN_REPOSITORY', 'run belongs to another repository'))
    if run.get('id') != run_id or run.get('html_url') != url:
        findings.append(_finding('CI_RUN_URL', 'run identity or URL differs'))
    return findings


def _run_workflow_findings(run, workflow_path):
    expected = (workflow_path if isinstance(workflow_path, dict)
                else {'path': workflow_path, 'name': 'validate-contracts'})
    run_path = run.get('path')
    if (run.get('name') != expected['name']
            or not isinstance(run_path, str)
            or run_path.split('@', 1)[0] != expected['path']):
        return [_finding('CI_RUN_WORKFLOW', 'run is not the expected validator')]
    return []


def verify_run(evidence, repository, current_run_id, fetch_run,
               workflow_path='.github/workflows/validate.yml'):
    """Validate one prior run using an injected read-only API lookup."""
    reference = _run_reference(evidence, repository)
    if reference is None:
        return [_finding('CI_RUN_REFERENCE', 'invalid run URL or head SHA')]
    run_id, url, sha = reference
    if run_id == current_run_id:
        return [_finding('CI_RUN_SELF', 'the current run cannot certify itself')]
    try:
        run = fetch_run(repository, run_id)
    except (OSError, ValueError, KeyError) as exc:
        return [_finding('CI_RUN_LOOKUP', 'run lookup failed: ' + str(exc))]
    if not isinstance(run, dict):
        return [_finding('CI_RUN_LOOKUP', 'run response is not an object')]
    findings = []
    if run.get('status') != 'completed' or run.get('conclusion') != 'success':
        findings.append(_finding('CI_RUN_NOT_SUCCESS', 'run is not completed successfully'))
    findings.extend(_run_identity_findings(run, repository, run_id, url, sha))
    findings.extend(_run_workflow_findings(run, workflow_path))
    return findings


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _fetch_run(token, repository, run_id):
    url = 'https://api.github.com/repos/{}/actions/runs/{}'.format(
        repository, run_id)
    req = request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
    })
    opener = request.build_opener(_NoRedirect)
    with opener.open(req, timeout=10) as response:
        return json.load(response)


def _git(root, *args):
    result = subprocess.run(['git', '--no-replace-objects', '--literal-pathspecs', '-C', str(root), *args],
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError('Git command failed: ' + ' '.join(args))
    return result.stdout


def _source_findings(root, source_sha, candidate_sha, specs_dir):
    if not _SHA.fullmatch(source_sha) or not _SHA.fullmatch(candidate_sha):
        return [_finding('CI_SOURCE_SHA', 'source or candidate SHA is invalid')]
    try:
        _git(root, 'merge-base', '--is-ancestor', source_sha, candidate_sha)
        changed = _git(root, 'diff', '--no-renames', '--name-only', '-z', source_sha,
                       candidate_sha).decode('utf-8').strip('\0').split('\0')
    except _GIT_ERRORS:
        return [_finding('CI_SOURCE_SHA', 'CI SHA is not an available ancestor')]
    return verify_closure_diff((path for path in changed if path), specs_dir)


def _spec_prefix(path, specs_dir):
    parent, _, filename = path.rpartition('/')
    match = re.fullmatch(_SPEC, filename) if parent == specs_dir else None
    return match.group(1) if match else None


def _changed_paths(root, base_sha, candidate_sha):
    if not _SHA.fullmatch(candidate_sha):
        raise ValueError('base or candidate SHA is invalid')
    if not base_sha:
        base_sha = _git(root, 'rev-parse', candidate_sha + '^').decode(
            'ascii').strip()
    if not _SHA.fullmatch(base_sha):
        raise ValueError('base or candidate SHA is invalid')
    common = _git(root, 'merge-base', base_sha, candidate_sha).decode(
        'ascii').strip()
    return _diff_paths(root, common, candidate_sha)


def _diff_paths(root, *revisions):
    return _git(root, 'diff', '--no-renames', '--name-only', '-z',
                *revisions).decode('utf-8').strip('\0').split('\0')


def _closures(paths, specs_dir, legacy):
    closures = {}
    for path in paths:
        match = _REPORT.fullmatch(path)
        prefix = match.group(1) if match else _spec_prefix(path, specs_dir)
        if prefix and prefix not in legacy:
            closures[prefix] = bool(match) or closures.get(prefix, False)
    return closures


def _blob(root, commit, path):
    raw = _git(root, 'ls-tree', '-z', commit, '--', path)
    if not raw:
        return None
    header, _, name = raw.partition(b'\t')
    mode, kind, oid = header.decode('ascii').split()
    if name != path.encode('utf-8') + b'\0' or kind != 'blob' or mode not in ('100644', '100755'):
        raise ValueError('expected a regular blob: ' + path)
    return _git(root, 'cat-file', 'blob', oid).decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')


def _working_text(root, path):
    local = root
    for part in path.split('/'):
        local = local / part
        if local.is_symlink() or getattr(local.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('nonregular checkout path: ' + path)
    if not local.is_file():
        raise ValueError('expected a regular checkout file: ' + path)
    return local.read_text(encoding='utf-8')


def _without_mark(line):
    checkbox = _CHECKBOX.match(line)
    if checkbox and _ID.match(checkbox.group(2)):
        start, end = checkbox.span(1)
        return line[:start] + ' ' + line[end:]
    return line


def _criteria_block(text):
    lines = text.split('\n')
    starts = [index for index, line in enumerate(lines)
              if line.strip() == '## Criterios de aceptación']  # ascii: allow
    if len(starts) != 1:
        raise ValueError('expected one criteria section')
    block = []
    for line in lines[starts[0] + 1:]:
        if line.startswith('## '):
            break
        block.append(_without_mark(line))
    return block


def _criteria_findings(root, revisions, spec, compare_local):
    source, candidate = revisions
    try:
        previous = _blob(root, source, spec)
        current = _blob(root, candidate, spec)
        if previous is None or current is None or (compare_local and _working_text(root, spec) != current):
            raise ValueError('criterion source is absent or differs from checkout')
        if _criteria(current, spec)[1] or _criteria_block(previous) != _criteria_block(current):
            raise ValueError('criteria differ from cited CI commit')
        return []
    except _GIT_ERRORS as exc:
        return [_finding('CI_CRITERIA_DRIFT', spec + ': ' + str(exc))]


def _closure_manifest(root, candidate, prefix, compare_local):
    path = 'docs/reports/' + prefix
    if _blob(root, candidate, path + '-REPORT.md') is None:
        return None
    name = path + '-EVIDENCE.json'
    raw = _blob(root, candidate, name)
    if raw is None or (compare_local and _working_text(root, name) != raw):
        raise ValueError('manifest is absent or differs from checkout: ' + name)
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('schema_version') != 1 or data.get('state') != 'verified_in_ci':
        raise ValueError('invalid closure manifest: ' + name)
    return data


def _verify_criteria(root, context, data, closure, compare_local):
    prefix, specs_dir = closure
    spec = data.get('spec')
    reference = _run_reference(data, context['repository'])
    if not reference or not isinstance(spec, str) or _spec_prefix(spec, specs_dir) != prefix:
        return [_finding('CI_EVIDENCE', 'invalid closure spec or run: ' + prefix)]
    return _criteria_findings(root, (reference[2], context['candidate_sha']), spec, compare_local)


def _remote_findings(root, context, token, data, specs_dir):
    findings = verify_run(data, context['repository'], context['current_run_id'],
                          lambda repo, run_id: _fetch_run(token, repo, run_id), context['workflow'])
    reference = _run_reference(data, context['repository'])
    if reference:
        findings.extend(_source_findings(root, reference[2], context['candidate_sha'], specs_dir))
    return findings


def _closure_candidates(root, context, specs_dir, legacy):
    candidate = context['candidate_sha']
    paths = _changed_paths(root, context.get('base_sha', ''), candidate)
    closures = _closures(paths, specs_dir, legacy)
    compare_local = _git(root, 'rev-parse', 'HEAD').decode('ascii').strip() == candidate.lower()
    if compare_local:
        for prefix in _closures(_diff_paths(root, 'HEAD'), specs_dir, legacy):
            closures.setdefault(prefix, False)
    return sorted(closures.items()), compare_local


def _audit_closures(root, context, token, specs_dir, selection):
    closures, compare_local = selection
    findings, checked = [], 0
    for prefix, needs_remote in closures:
        try:
            data = _closure_manifest(root, context['candidate_sha'], prefix, compare_local)
        except _GIT_ERRORS as exc:
            findings.append(_finding('CI_EVIDENCE', '{}: {}'.format(prefix, exc)))
            continue
        if data is None:
            continue
        findings.extend(_verify_criteria(root, context, data, (prefix, specs_dir), compare_local))
        if needs_remote:
            if not token:
                return findings + [_finding('CI_TOKEN', 'GITHUB_TOKEN with actions: read is required')], checked
            findings.extend(_remote_findings(root, context, token, data, specs_dir))
            checked += 1
    return findings, checked


def verify_project(root, context, token, policy_path='completion-legacy.json',
                   specs_dir='specs'):
    """Verify closures and check criteria against the commit executed by CI."""
    root = Path(root).resolve()
    repository = context['repository']
    structural = validate_completion(root, policy_path, specs_dir, repository)
    if structural:
        return structural, 0
    policy, error = _load_policy(root / policy_path, repository)
    if error:
        return [error], 0
    try:
        directory = (root / specs_dir).resolve().relative_to(root).as_posix()
        directory = '' if directory == '.' else directory
        selection = _closure_candidates(root, context, directory, policy[1])
    except _GIT_ERRORS:
        return [_finding('CI_BASE_SHA', 'cannot identify changed closures')], 0
    return _audit_closures(root, context, token, directory, selection)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--repository', required=True)
    parser.add_argument('--current-run-id', required=True, type=int)
    parser.add_argument('--candidate-sha', required=True)
    parser.add_argument('--base-sha', default='')
    parser.add_argument('--workflow-path', default='.github/workflows/validate.yml')
    parser.add_argument('--workflow-name', default='validate-contracts')
    parser.add_argument('--policy', default='completion-legacy.json')
    parser.add_argument('--specs-dir', default='specs')
    args = parser.parse_args(argv)
    if not _REPOSITORY.fullmatch(args.repository):
        parser.error('--repository must be OWNER/REPO')
    context = {'repository': args.repository,
               'current_run_id': args.current_run_id,
               'candidate_sha': args.candidate_sha,
               'base_sha': args.base_sha,
               'workflow': {'path': args.workflow_path,
                            'name': args.workflow_name}}
    findings, checked = verify_project(args.repo_root, context,
                                       os.environ.get('GITHUB_TOKEN'),
                                       args.policy, args.specs_dir)
    for item in findings:
        print('ERROR [{}] {}'.format(item['rule'], item['msg']))
    print('Summary: verified={} FAIL={}'.format(checked, len(findings)))
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
