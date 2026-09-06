"""Validate imports against AWS in an isolated local backend without applying.

Run with Terraform on PATH and AWS_PROFILE set. Writes only ignored .private
files; both AWS infrastructure and remote Terraform state remain unchanged.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
from release import ROOT, aws, plan_changes


def main():
    work = ROOT / '.private' / 'baseline'
    work.mkdir(parents=True, exist_ok=True)
    for source in list(ROOT.glob('*.tf')) + list(ROOT.glob('*.tf.json')) + [ROOT / '.terraform.lock.hcl']:
        if source.name == 'versions.tf':
            (work / source.name).write_text(source.read_text().replace('backend "s3" {}', ''), encoding='utf-8')
        else:
            shutil.copyfile(source, work / source.name)
    config = json.loads((ROOT / 'deployment.json').read_text())
    if config['component'] == 'assistant':
        function = aws('lambda', 'get-function-configuration', '--function-name', 'cg-production-chatbot')
        (work / 'runtime.auto.tfvars.json').write_text(json.dumps({
            'lambda_environment': function['Environment']['Variables']}), encoding='utf-8')
    def terraform(*args):
        result = subprocess.run(['terraform', *args], cwd=work, capture_output=True, text=True)
        (work / (args[0] + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'Terraform {args[0]} failed; inspect the private log locally')
        return result.stdout
    terraform('init', '-input=false', '-lockfile=readonly')
    terraform('plan', '-input=false', '-out=baseline.tfplan')
    plan = json.loads(terraform('show', '-json', 'baseline.tfplan'))
    plan_changes(plan, adoption=True)
    imports = sum('importing' in item['change'] for item in plan.get('resource_changes', []))
    sensitivity_updates = sum(item['change']['actions'] == ['update'] for item in plan.get('resource_changes', []))
    print(f'{imports} imports; no effective resource-value changes; {sensitivity_updates} sensitivity-only updates.')
    print('No apply performed. Review .private/baseline/baseline.tfplan locally.')


if __name__ == '__main__':
    main()
