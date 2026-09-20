#!/usr/bin/env python3
"""Deliver a minimal, signed KDD lifecycle event to an opt-in HTTPS relay."""

import hashlib
import hmac
import json
import os
import sys
import urllib.request


def main():
    url = os.environ.get('KDD_WEBHOOK_URL', '')
    secret = os.environ.get('KDD_WEBHOOK_SECRET', '')
    if not url or not secret:
        return 0
    if not url.startswith('https://'):
        print('KDD webhook delivery requires an HTTPS URL', file=sys.stderr)
        return 0
    try:
        source = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    payload = {
        'event': str(source.get('hook_event_name', 'unknown')),
        'session_id': str(source.get('session_id', '')),
        'cwd': str(source.get('cwd', '')),
    }
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json', 'X-KDD-Signature': f'sha256={signature}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=5):
            pass
    except OSError:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
