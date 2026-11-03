import json
import shutil
import subprocess
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / 'terraform/hooks/guard-tf.sh'

pytestmark = pytest.mark.skipif(shutil.which('jq') is None, reason='jq is required by the guard hook')

BLOCKED = [
    'terraform apply',
    'terraform apply -auto-approve',
    'terraform destroy',
    'terraform import aws_instance.x i-123',
    'terraform taint aws_instance.x',
    'terraform untaint aws_instance.x',
    'terraform force-unlock 1234',
    'terraform state mv a b',
    'terraform state rm a',
    'terraform state push terraform.tfstate',
    'terraform state replace-provider a/b c/d',
    'terraform refresh',
    'terraform workspace delete staging',
    'terraform -chdir=envs/prod apply -auto-approve',
    'terraform -chdir envs/prod destroy',
    'terraform -no-color apply',
    '/usr/local/bin/terraform apply',
    'sudo terraform destroy',
    'timeout 600 terraform apply',
    'timeout -s KILL 30s terraform apply',
    'nice terraform apply',
    'nice -n 10 terraform destroy',
    'env TF_LOG=debug terraform apply',
    'env -i PATH=/usr/bin terraform import a.b id',
    'TF_VAR_x=1 terraform apply',
    'bash -c "terraform apply"',
    "sh -c 'terraform destroy'",
    'bash -lc "cd envs/prod && terraform apply -auto-approve"',
    'echo ok; terraform apply',
    'terraform plan && terraform apply',
    'terraform plan | tee out.txt; terraform destroy',
    '(terraform apply)',
    '( cd envs/prod && terraform apply )',
    '$(terraform apply)',
    'echo x | xargs terraform apply',
    'xargs -n1 terraform destroy',
    "find . -name '*.tf' | xargs -I{} terraform state rm {}",
    'tofu apply',
    'tofu state rm a',
    'nohup terraform apply &',
    'terraform apply # just kidding',
]

ALLOWED = [
    'terraform plan',
    'terraform -chdir=envs/prod plan',
    'terraform validate',
    'terraform fmt -recursive',
    'terraform init -backend=false',
    'terraform init -upgrade',
    'terraform state list',
    'terraform state show aws_instance.x',
    'terraform state pull',
    'terraform show',
    'terraform show -json tfplan',
    'terraform output',
    'terraform output -json',
    'terraform providers',
    'terraform providers lock -platform=linux_amd64',
    'terraform version',
    'terraform -version',
    'terraform test',
    'terraform graph',
    'terraform workspace list',
    'tofu plan',
    'timeout 600 terraform plan',
    'nice terraform validate',
    'env TF_LOG=debug terraform plan',
    'bash -c "terraform plan"',
    "sh -c 'terraform fmt -check'",
    'echo "run terraform apply later"',
    'echo terraform destroy',
    'git commit -m "docs: explain terraform apply flow"',
    'grep -r "terraform apply" docs/',
    'cat README.md # terraform apply is user-run',
    'terraform-ls serve',
    'terraform-docs markdown table .',
    'ls',
    '',
]


def run_guard(payload):
    return subprocess.run(
        ['bash', str(GUARD)], input=json.dumps(payload), capture_output=True, text=True, timeout=10,
    )


@pytest.mark.parametrize('command', BLOCKED)
def test_blocked(command):
    res = run_guard({'tool_input': {'command': command}})
    assert res.returncode == 2, res.stderr
    assert res.stderr.strip()


@pytest.mark.parametrize('command', ALLOWED)
def test_allowed(command):
    res = run_guard({'tool_input': {'command': command}})
    assert res.returncode == 0, res.stderr


def test_missing_command_key():
    assert run_guard({'tool_input': {}}).returncode == 0
