"""Resolve the currently configured application image to an immutable ECR URI."""
import json
from release import ROOT, aws


def main():
    config = json.loads((ROOT / 'deployment.json').read_text())
    if config['component'] == 'assistant':
        uri = aws('lambda', 'get-function', '--function-name', 'cg-production-chatbot')['Code']['ResolvedImageUri']
    else:
        definitions = aws('batch', 'describe-job-definitions', '--job-definition-name', 'cg-metadata-job', '--status', 'ACTIVE')['jobDefinitions']
        uri = max(definitions, key=lambda item: item['revision'])['containerProperties']['image']
        if '@sha256:' not in uri:
            repository, tag = uri.rsplit(':', 1)
            image = aws('ecr', 'describe-images', '--repository-name', repository.rsplit('/', 1)[-1], '--image-ids', 'imageTag=' + tag)
            uri = repository + '@' + image['imageDetails'][0]['imageDigest']
    if not uri.startswith(config['ecr_uri'] + '@sha256:'):
        raise ValueError('Current image is outside the expected ECR repository')
    print(uri)


if __name__ == '__main__':
    main()
