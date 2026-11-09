"""Post-deploy smoke checks for the live site. Standard library only; needs no credentials.

Usage:  SMOKE_BASE_URL=https://example.cloudfront.net python tests/smoke/smoke.py
        python tests/smoke/smoke.py https://example.cloudfront.net

Exits non-zero if any check fails. Each check is retried because a fresh CloudFront invalidation and a
cold Lambda both take a little while to settle.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

USER_AGENT = 'cg-assistant-smoke/1.0'
ATTEMPTS = int(os.environ.get('SMOKE_ATTEMPTS', '6'))
DELAY_SECONDS = float(os.environ.get('SMOKE_DELAY_SECONDS', '10'))


class SmokeFailure(Exception):
    """A check ran and the site's answer was wrong."""


def fetch(url, timeout=30):
    """GET a URL and return (status, body). HTTP error statuses are returned, not raised."""
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def expect_status(status, expected, what):
    if status != expected:
        raise SmokeFailure(f'{what}: expected HTTP {expected}, got {status}')


def check_index(base, get):
    """The SPA shell is served from S3 through CloudFront."""
    status, body = get(f'{base}/')
    expect_status(status, 200, 'GET /')
    if b'id="root"' not in body:
        raise SmokeFailure('GET /: response does not look like the app shell (no #root element)')


def check_runtime_config(base, get):
    """Terraform generates the real config.json; the copy in the repo is an empty placeholder."""
    status, body = get(f'{base}/config.json')
    expect_status(status, 200, 'GET /config.json')
    try:
        config = json.loads(body)
    except ValueError as error:
        raise SmokeFailure(f'GET /config.json: not valid JSON ({error})') from error
    missing = [key for key in ('cognitoDomain', 'cognitoClientId') if not config.get(key)]
    if missing:
        raise SmokeFailure(f'GET /config.json: empty or missing {", ".join(missing)}')


def check_health(base, get):
    """CloudFront to API Gateway to Lambda."""
    status, body = get(f'{base}/api/health')
    expect_status(status, 200, 'GET /api/health')
    try:
        payload = json.loads(body)
    except ValueError as error:
        raise SmokeFailure(f'GET /api/health: not valid JSON ({error})') from error
    if payload.get('status') != 'ok':
        raise SmokeFailure(f'GET /api/health: unexpected body {payload!r}')


def check_authorizer(base, get):
    """A protected route must reject anonymous callers with 401, proving the JWT authorizer is attached."""
    status, _ = get(f'{base}/api/conversations')
    expect_status(status, 401, 'GET /api/conversations without a token')


CHECKS = [
    ('app shell', check_index),
    ('runtime config', check_runtime_config),
    ('api health', check_health),
    ('authorizer rejects anonymous', check_authorizer),
]


def run_checks(base, get=fetch, attempts=ATTEMPTS, delay=DELAY_SECONDS, sleep=time.sleep, log=print):
    """Run every check with retries. Returns a list of (name, passed, detail)."""
    base = base.rstrip('/')
    results = []
    for name, check in CHECKS:
        detail = ''
        for attempt in range(1, attempts + 1):
            try:
                check(base, get)
                detail = ''
                break
            except (SmokeFailure, OSError) as error:  # OSError covers URLError, timeouts, resets
                detail = str(error)
                if attempt < attempts:
                    log(f'  retry {attempt}/{attempts - 1} for "{name}": {detail}')
                    sleep(delay)
        passed = detail == ''
        results.append((name, passed, detail))
        log(f'{"PASS" if passed else "FAIL"}  {name}' + (f': {detail}' if detail else ''))
    return results


def main(argv):
    base = argv[1] if len(argv) > 1 else os.environ.get('SMOKE_BASE_URL', '')
    if not base.startswith('https://'):
        print('Set SMOKE_BASE_URL (or pass the URL) to an https:// address.', file=sys.stderr)
        return 2
    results = run_checks(base)
    failed = [name for name, passed, _ in results if not passed]
    print(f'{len(results) - len(failed)}/{len(results)} smoke checks passed against {base}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
