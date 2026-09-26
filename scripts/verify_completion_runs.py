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

from validate_completion import validate_completion


_SHA = re.compile(r'[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?')
_REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
_SPEC = re.compile(r'specs/CONTRACT-[0-9]+-[^/]+\.md')
_REPORT = re.compile(r'docs/reports/CONTRACT-[0-9]+-(?:REPORT\.md|EVIDENCE\.json)')


def _finding(rule, message):
    return {'rule': rule, 'msg': message}


def verify_closure_diff(changed_paths):
    """Reject code or oracle changes after the run that was cited."""
    findings = []
    for path in changed_paths:
        allowed = (path == 'CHANGELOG.md' or _SPEC.fullmatch(path)
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
    result = subprocess.run(['git', '-C', str(root), *args],
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError('Git command failed: ' + ' '.join(args))
    return result.stdout


def _source_findings(root, source_sha, candidate_sha):
    if not _SHA.fullmatch(source_sha) or not _SHA.fullmatch(candidate_sha):
        return [_finding('CI_SOURCE_SHA', 'source or candidate SHA is invalid')]
    try:
        _git(root, 'merge-base', '--is-ancestor', source_sha, candidate_sha)
        changed = _git(root, 'diff', '--name-only', '-z', source_sha,
                       candidate_sha).decode('utf-8').strip('\0').split('\0')
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return [_finding('CI_SOURCE_SHA', 'CI SHA is not an available ancestor')]
    return verify_closure_diff(path for path in changed if path)


def _changed_manifests(root, base_sha, candidate_sha):
    if not _SHA.fullmatch(candidate_sha):
        raise ValueError('base or candidate SHA is invalid')
    if not base_sha:
        base_sha = _git(root, 'rev-parse', candidate_sha + '^').decode(
            'ascii').strip()
    if not _SHA.fullmatch(base_sha):
        raise ValueError('base or candidate SHA is invalid')
    common = _git(root, 'merge-base', base_sha, candidate_sha).decode(
        'ascii').strip()
    paths = _git(root, 'diff', '--name-only', '--diff-filter=AMRC', '-z',
                 common, candidate_sha).decode('utf-8').strip('\0').split('\0')
    return sorted(Path(root) / path for path in paths
                  if _REPORT.fullmatch(path) and path.endswith('-EVIDENCE.json'))


def verify_project(root, context, token, policy_path='completion-legacy.json',
                   specs_dir='specs'):
    """Verify every new closure after the local structural gate succeeds."""
    repository = context['repository']
    structural = validate_completion(root, policy_path, specs_dir, repository)
    if structural:
        return structural, 0
    try:
        manifests = _changed_manifests(root, context.get('base_sha', ''),
                                       context['candidate_sha'])
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return [_finding('CI_BASE_SHA', 'cannot identify changed closures')], 0
    if not manifests:
        return [], 0
    if not token:
        return [_finding('CI_TOKEN', 'GITHUB_TOKEN with actions: read is required')], 0
    findings = []
    for path in manifests:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            findings.append(_finding('CI_EVIDENCE', '{}: {}'.format(path, exc)))
            continue
        run_findings = verify_run(
            data, repository, context['current_run_id'],
            lambda repo, run_id: _fetch_run(token, repo, run_id),
            context['workflow'])
        findings.extend(run_findings)
        ci = data.get('ci') if isinstance(data, dict) else None
        if isinstance(ci, dict) and isinstance(ci.get('head_sha'), str):
            findings.extend(_source_findings(root, ci['head_sha'],
                                             context['candidate_sha']))
    return findings, len(manifests)


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
