import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SEMGREP_SCRIPTS = PLUGIN / 'skills/semgrep/scripts'
SARIF_RESOURCES = PLUGIN / 'skills/sarif-parsing/resources'
CODEQL_SCRIPTS = PLUGIN / 'skills/codeql/scripts'

sys.path.insert(0, str(SARIF_RESOURCES))
sys.path.insert(0, str(SEMGREP_SCRIPTS))
sys.path.insert(0, str(CODEQL_SCRIPTS))


def write_exe(path, text):
    path.write_text(text)
    path.chmod(0o755)
    return path


def run(cmd, env=None, cwd=None, **kw):
    full = dict(os.environ)
    if env:
        full.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=full, cwd=cwd, **kw)


def path_without(*binaries):
    """PATH with the directories holding the named binaries removed."""
    dirs = []
    for d in os.environ.get('PATH', '').split(os.pathsep):
        if any((Path(d) / b).exists() for b in binaries):
            continue
        dirs.append(d)
    return os.pathsep.join(dirs)


@pytest.fixture
def stub_bin(tmp_path):
    d = tmp_path / 'stub-bin'
    d.mkdir()
    return d


def require(binary):
    if shutil.which(binary) is None:
        pytest.skip(f'not run: {binary} missing')
