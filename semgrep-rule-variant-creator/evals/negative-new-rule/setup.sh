#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Tomas Brandt" GIT_AUTHOR_EMAIL="tomas@example.org"
export GIT_COMMITTER_NAME="Tomas Brandt" GIT_COMMITTER_EMAIL="tomas@example.org"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p sast/flask-os-system

cat > sast/flask-os-system/flask-os-system.yaml <<'YAML'
rules:
  - id: flask-os-system
    languages: [python]
    severity: ERROR
    message: Request data reaches a shell command string. Quote it with shlex.quote or avoid the shell.
    mode: taint
    pattern-sources:
      - pattern: flask.request.args.get(...)
      - pattern: flask.request.form.get(...)
    pattern-sanitizers:
      - pattern: shlex.quote(...)
    pattern-sinks:
      - pattern: os.system(...)
      - pattern: subprocess.call(..., shell=True, ...)
      - pattern: subprocess.run(..., shell=True, ...)
    metadata:
      category: security
      cwe: "CWE-78: OS Command Injection"
YAML

cat > sast/flask-os-system/flask-os-system.py <<'PY'
import os
import shlex
import subprocess

import flask


def lookup():
    name = flask.request.args.get("name")
    # ruleid: flask-os-system
    os.system("nslookup " + name)


def archive():
    target = flask.request.form.get("target")
    # ruleid: flask-os-system
    subprocess.run("tar czf out.tgz " + target, shell=True)


def quoted():
    name = flask.request.args.get("name")
    # ok: flask-os-system
    os.system("nslookup " + shlex.quote(name))


def argv_list():
    name = flask.request.args.get("name")
    # ok: flask-os-system
    subprocess.run(["nslookup", name])


def constant():
    # ok: flask-os-system
    os.system("uptime")
PY

cat > app.py <<'PY'
import flask

app = flask.Flask(__name__)


@app.route("/dns")
def dns():
    return "ok"
PY
git add -A
git commit -q -m "sast: flask command injection rule"
