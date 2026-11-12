import os
import shlex
import subprocess
import sys

from flask import Flask, render_template_string, request

app = Flask(__name__)


@app.post("/unpack")
def unpack():
    name = request.args.get("name")
    # ruleid: variant-taint-python
    subprocess.run("gzip -d /srv/in/" + name, shell=True, check=True)
    return ""


@app.post("/count")
def count():
    # ok: variant-taint-python
    subprocess.run(["wc", "-l", request.form["file"]], check=True)
    return ""


@app.post("/quoted")
def quoted():
    # ok: variant-taint-python
    subprocess.run("wc -l " + shlex.quote(request.form["file"]), shell=True, check=True)
    return ""


def report(cur):
    owner = sys.argv[1]
    # ruleid: variant-taint-python
    cur.execute("SELECT * FROM jobs WHERE owner = '%s'" % owner)
    # ok: variant-taint-python
    cur.execute("SELECT * FROM jobs WHERE owner = %s", (owner,))


def config():
    # ruleid: variant-taint-python
    return open(os.environ["DEMO_CONFIG"]).read()


@app.get("/greet")
def greet():
    # ruleid: variant-taint-python
    return render_template_string("<p>" + request.args["who"] + "</p>")


def constant():
    # ok: variant-taint-python
    os.system("uptime")
