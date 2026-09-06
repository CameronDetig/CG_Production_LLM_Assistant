"""Read AWS configuration and prepare import blocks; never mutates AWS.

Uses the AWS CLI's authenticated profile. Raw configuration is kept under
.private because Lambda configuration can contain secrets. Never print it.
"""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile')
    parser.add_argument('--component', choices=['extractor', 'assistant'], required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    private = root / '.private'
    private.mkdir(exist_ok=True)
    imports = []
    inventory = {}

    def aws(*command, optional=False):
        cmd = ['aws', *command, '--region', 'us-east-1', '--output', 'json', '--no-cli-pager']
        if args.profile:
            cmd += ['--profile', args.profile]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            if optional and any(code in result.stderr for code in [
                'NoSuchBucketPolicy', 'NoSuchLifecycleConfiguration',
                'NoSuchCORSConfiguration', 'NoSuchPublicAccessBlockConfiguration',
                'RepositoryPolicyNotFoundException', 'LifecyclePolicyNotFoundException',
            ]):
                return None
            raise RuntimeError(f'AWS inventory failed: {command[0]} {command[1]}')
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def add(kind, name, identifier):
        imports.append({'to': f'{kind}.{name}', 'id': identifier})

    def role(name, label):
        add('aws_iam_role', label, name)
        for p in aws('iam', 'list-attached-role-policies', '--role-name', name)['AttachedPolicies']:
            pname = p['PolicyName'].replace('-', '_')
            add('aws_iam_role_policy_attachment', label + '_' + pname, name + '/' + p['PolicyArn'])
            if ':aws:policy/' not in p['PolicyArn']:
                add('aws_iam_policy', label + '_' + pname, p['PolicyArn'])
        for p in aws('iam', 'list-role-policies', '--role-name', name)['PolicyNames']:
            add('aws_iam_role_policy', label + '_' + p.replace('-', '_'), name + ':' + p)

    identity = aws('sts', 'get-caller-identity')
    if identity['Account'] != '001879457662':
        raise RuntimeError('Refusing inventory of an unexpected AWS account')
    repo = 'cg-metadata-extractor' if args.component == 'extractor' else 'cg-chatbot'
    add('aws_ecr_repository', 'application', repo)
    for action, kind in [('get-lifecycle-policy', 'aws_ecr_lifecycle_policy'),
                         ('get-repository-policy', 'aws_ecr_repository_policy')]:
        if aws('ecr', action, '--repository-name', repo, optional=True):
            add(kind, 'application', repo)
    if args.component == 'extractor':
        vpc = 'vpc-04bb7be45c9d6b7f7'
        add('aws_vpc', 'production', vpc)
        for s in aws('ec2', 'describe-subnets', '--filters', f'Name=vpc-id,Values={vpc}')['Subnets']:
            add('aws_subnet', s['AvailabilityZone'].replace('-', '_'), s['SubnetId'])
        for r in aws('ec2', 'describe-route-tables', '--filters', f'Name=vpc-id,Values={vpc}')['RouteTables']:
            add('aws_route_table', 'production', r['RouteTableId'])
        add('aws_internet_gateway', 'production', 'igw-0aeac8f9ebd5d5aad')
        for name, sid in [('batch', 'sg-0b84f22c177e4ec4a'), ('database', 'sg-0b0227fe8f2b2e60f'),
                          ('assistant', 'sg-0412872e9f94acb2b')]:
            add('aws_security_group', name, sid)
        add('aws_db_subnet_group', 'production', 'default-vpc-04bb7be45c9d6b7f7')
        add('aws_db_instance', 'metadata', 'cg-metadata-db')
        for name, bucket in [('assets', 'cg-production-data'), ('thumbnails', 'cg-production-data-thumbnails')]:
            add('aws_s3_bucket', name, bucket)
            for action, kind in [('get-bucket-versioning', 'aws_s3_bucket_versioning'),
                                 ('get-bucket-encryption', 'aws_s3_bucket_server_side_encryption_configuration'),
                                 ('get-public-access-block', 'aws_s3_bucket_public_access_block'),
                                 ('get-bucket-policy', 'aws_s3_bucket_policy'),
                                 ('get-bucket-lifecycle-configuration', 'aws_s3_bucket_lifecycle_configuration'),
                                 ('get-bucket-cors', 'aws_s3_bucket_cors_configuration')]:
                value = aws('s3api', action, '--bucket', bucket, optional=True)
                if value:
                    add(kind, name, bucket)
        secret = aws('secretsmanager', 'describe-secret', '--secret-id', 'cg-metadata-db/database-url')
        add('aws_secretsmanager_secret', 'database', secret['ARN'])
        add('aws_batch_compute_environment', 'extractor', 'arn:aws:batch:us-east-1:001879457662:compute-environment/cg-metadata-compute')
        add('aws_batch_job_queue', 'extractor', 'arn:aws:batch:us-east-1:001879457662:job-queue/cg-metadata-queue')
        jobs = aws('batch', 'describe-job-definitions', '--job-definition-name', 'cg-metadata-job', '--status', 'ACTIVE')['jobDefinitions']
        job = max(jobs, key=lambda j: j['revision'])
        inventory['batch'] = job
        add('aws_batch_job_definition', 'extractor', job['jobDefinitionArn'])
        role('CGMetadataExtractorRole', 'extractor')
        add('aws_cloudwatch_log_group', 'application', '/aws/batch/job')
    else:
        function = aws('lambda', 'get-function', '--function-name', 'cg-production-chatbot')
        inventory['lambda'] = function
        # Keep environment values in an ignored input file, not generated source.
        (private / 'runtime.auto.tfvars.json').write_text(json.dumps({
            'lambda_environment': function['Configuration']['Environment']['Variables']
        }, indent=2) + '\n', encoding='utf-8')
        add('aws_lambda_function', 'assistant', 'cg-production-chatbot')
        add('aws_lambda_function_url', 'assistant', 'cg-production-chatbot')
        add('aws_lambda_permission', 'function_url', 'cg-production-chatbot/FunctionURLAllowPublicAccess')
        role('cg-chatbot-lambda-role', 'assistant')
        pool = 'us-east-1_olfysYmLE'
        add('aws_cognito_user_pool', 'users', pool)
        add('aws_cognito_user_pool_client', 'assistant', pool + '/7fjti9ulrj9rgoq0lgs9g8eobg')
        add('aws_cognito_user_pool_domain', 'users', 'us-east-1olfysymle')
        add('aws_dynamodb_table', 'conversations', 'cg-chatbot-conversations')
        add('aws_cloudwatch_log_group', 'application', '/aws/lambda/cg-production-chatbot')
    # Raw material stays ignored. Import IDs alone are safe to review and commit.
    (private / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n', encoding='utf-8')
    (root / 'imports.tf.json').write_text(json.dumps({'import': imports}, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {len(imports)} import blocks for {args.component}; AWS unchanged.')


if __name__ == '__main__':
    main()
