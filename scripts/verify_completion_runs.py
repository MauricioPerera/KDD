#!/usr/bin/env python3
"""Verify a completed GitHub Actions run before closing a project contract."""


def verify_run(evidence, repository, current_run_id, fetch_run,
               workflow_path='.github/workflows/validate.yml'):
    raise NotImplementedError


def verify_closure_diff(changed_paths):
    raise NotImplementedError
