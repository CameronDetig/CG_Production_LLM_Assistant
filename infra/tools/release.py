"""Private Terraform plans and explicit, provenance-checked deployment.

AWS CLI credentials come from GitHub OIDC or the operator's profile. Never
print Terraform's raw plan JSON, Lambda environment, or captured CLI errors.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.private'


def command(args, *, json_output=False):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        PRIVATE.mkdir(exist_ok=True)
        (PRIVATE / 'last-error.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        raise RuntimeError(f'{args[0]} {args[1]} failed; details kept in .private/last-error.log')
    return json.loads(result.stdout) if json_output else result.stdout.strip()


def aws(*args):
    return command(['aws', *args, '--region', 'us-east-1', '--output', 'json', '--no-cli-pager'], json_output=True)


def plan_changes(plan, *, adoption=False):
    """Fail closed on destructive changes; never include resource values in output."""
    changes = []
    for item in plan.get('resource_changes', []):
        change = item['change']
        actions = change['actions']
        if 'delete' in actions:
            raise ValueError(f"Destruction/replacement requires a separate migration: {item['address']}")
        if actions in [['no-op'], ['read']]:
            continue
        # Import can report a sensitivity-only change even when every value matches.
        if change.get('before') == change.get('after') and not contains_unknown(change.get('after_unknown', {})):
            continue
        if adoption:
            raise ValueError(f"Import baseline changes live configuration: {item['address']}")
        changes.append({'address': item['address'], 'actions': actions})
    return changes


def contains_unknown(value):
    if isinstance(value, dict):
        return any(contains_unknown(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_unknown(item) for item in value)
    return value is True


def validate_run(run, config):
    if (run['conclusion'] != 'success' or run['head_branch'] != 'main'
            or run['event'] not in ['push', 'workflow_dispatch']
            or run['path'] != config['workflow']
            or run['repository']['full_name'] != config['repository']):
        raise ValueError('Only a successful release-plan run from this repository main branch can be applied')


def validate_manifest(manifest, run, config, now):
    if manifest['commit'] != run['head_sha'] or manifest['repository'] != config['repository']:
        raise ValueError('Plan source does not match the approved GitHub run')
    if not 0 <= now - manifest['created_at'] < 86400:
        raise ValueError('Plan has expired; create and approve a new plan')


def object_key(run_id, attempt, filename):
    if not str(run_id).isdigit() or not str(attempt).isdigit():
        raise ValueError('Run ID and attempt must be numeric')
    return f'plans/{run_id}/{attempt}/{filename}'


def download(bucket, key, destination):
    aws('s3api', 'get-object', '--bucket', bucket, '--key', key, str(destination))


def upload(bucket, key, source):
    # A rerun has a different attempt prefix. Never overwrite a reviewed plan.
    aws('s3api', 'put-object', '--bucket', bucket, '--key', key,
        '--body', str(source), '--server-side-encryption', 'AES256', '--if-none-match', '*')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'verify', 'apply', 'smoke'])
    parser.add_argument('--image-uri')
    parser.add_argument('--run-id')
    parser.add_argument('--adoption', action='store_true')
    args = parser.parse_args()
    PRIVATE.mkdir(exist_ok=True)
    config = json.loads((ROOT / 'deployment.json').read_text())
    bucket = config['state_bucket']
    if args.action == 'smoke':
        expected_image = command(['terraform', 'output', '-raw', 'image_uri'])
        if config['component'] == 'assistant':
            data = aws('lambda', 'get-function', '--function-name', 'cg-production-chatbot')
            if data['Configuration']['State'] != 'Active' or data['Configuration']['LastUpdateStatus'] != 'Successful':
                raise ValueError('Lambda update is not healthy')
            actual_image = data['Code']['ResolvedImageUri'] if '@sha256:' in expected_image else data['Code']['ImageUri']
            if actual_image != expected_image:
                raise ValueError('Lambda image differs from the applied Terraform state')
            print('Lambda configuration is active. Run the documented authenticated smoke test before accepting the release.')
        else:
            definition = command(['terraform', 'output', '-raw', 'job_definition_arn'])
            data = aws('batch', 'describe-job-definitions', '--job-definitions', definition)
            if (len(data['jobDefinitions']) != 1 or data['jobDefinitions'][0]['status'] != 'ACTIVE'
                    or data['jobDefinitions'][0]['containerProperties']['image'] != expected_image):
                raise ValueError('Batch job definition does not match the applied Terraform state')
            print('Batch definition is active. No asset scan was submitted.')
        return
    if args.action in ['verify', 'apply']:
        if not args.run_id or not args.run_id.isdigit():
            raise ValueError('A numeric plan run ID is required')
        run = command(['gh', 'api', f"repos/{config['repository']}/actions/runs/{args.run_id}"], json_output=True)
        validate_run(run, config)
        key = object_key(args.run_id, run['run_attempt'], 'manifest.json')
        manifest_file = PRIVATE / 'manifest.json'
        download(bucket, key, manifest_file)
        manifest = json.loads(manifest_file.read_text())
        validate_manifest(manifest, run, config, time.time())
        if args.action == 'verify':
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
                out.write(f"commit={manifest['commit']}\n")
            return
        commit = command(['git', 'rev-parse', 'HEAD'])
        if commit != manifest['commit']:
            raise ValueError('Checkout differs from the approved plan commit')
        saved = PRIVATE / 'release.tfplan'
        download(bucket, object_key(args.run_id, run['run_attempt'], 'release.tfplan'), saved)
        if hashlib.sha256(saved.read_bytes()).hexdigest() != manifest['sha256']:
            raise ValueError('Plan checksum mismatch')
        command(['terraform', 'init', '-input=false', '-lockfile=readonly', '-backend-config=backend.hcl'])
        # Terraform rejects stale state serials. Do not re-plan here.
        command(['terraform', 'apply', '-input=false', str(saved)])
        print('Applied the approved saved plan.')
        return
    image = args.image_uri
    if not args.adoption and (not image or not re.fullmatch(re.escape(config['ecr_uri']) + r'@sha256:[a-f0-9]{64}', image)):
        raise ValueError('Release requires an immutable image digest from this repository')
    variables = {}
    if config['component'] == 'assistant':
        # Preserve current secret delivery. Raw values never leave private files/state.
        function = aws('lambda', 'get-function-configuration', '--function-name', 'cg-production-chatbot')
        variables['lambda_environment'] = function['Environment']['Variables']
        variables['use_shared_contract'] = not args.adoption
    else:
        variables['publish_shared_contract'] = not args.adoption
    if image:
        variables['image_uri'] = image
    runtime = PRIVATE / 'runtime.tfvars.json'
    runtime.write_text(json.dumps(variables), encoding='utf-8')
    command(['terraform', 'init', '-input=false', '-lockfile=readonly', '-backend-config=backend.hcl'])
    saved = PRIVATE / 'release.tfplan'
    command(['terraform', 'plan', '-input=false', '-lock-timeout=60s', f'-var-file={runtime}', f'-out={saved}'])
    plan = command(['terraform', 'show', '-json', str(saved)], json_output=True)
    changes = plan_changes(plan, adoption=args.adoption)
    summary = json.dumps(changes, indent=2)
    print(summary)
    if 'GITHUB_STEP_SUMMARY' in os.environ:
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as out:
            out.write('Review the affected resources below. The full sensitive plan is stored privately in S3.\n\n```json\n' + summary + '\n```\n')
    manifest = {
        'commit': command(['git', 'rev-parse', 'HEAD']),
        'repository': config['repository'],
        'sha256': hashlib.sha256(saved.read_bytes()).hexdigest(),
        'created_at': int(time.time()), 'image_uri': image,
    }
    manifest_file = PRIVATE / 'manifest.json'
    manifest_file.write_text(json.dumps(manifest), encoding='utf-8')
    run_id = os.environ['GITHUB_RUN_ID']
    attempt = os.environ['GITHUB_RUN_ATTEMPT']
    upload(bucket, object_key(run_id, attempt, 'release.tfplan'), saved)
    upload(bucket, object_key(run_id, attempt, 'manifest.json'), manifest_file)
    print(f'Plan ready for approval: GitHub run {run_id}, attempt {attempt}. Expires in 24 hours.')


if __name__ == '__main__':
    main()
