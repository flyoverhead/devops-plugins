"""Fixtures: the scripts as modules and CLIs, an isolated git, and a campaign driven end to end."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "skills" / "regression-hunt" / "scripts"
PY = sys.executable
sys.path.insert(0, str(SCRIPTS))


def load(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def isolated_git(tmp_path, monkeypatch):
    cfg = tmp_path / "_gitconfig"
    cfg.write_text("[user]\n\tname = Test Person\n\temail = test@example.invalid\n"
                   "[commit]\n\tgpgsign = false\n[core]\n\thooksPath = /dev/null\n"
                   "[init]\n\tdefaultBranch = main\n")
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(where, *args) -> str:
    done = subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def cli(script, *args, ok=None):
    done = subprocess.run([PY, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True)
    if ok is True:
        assert done.returncode == 0, done.stderr
    if ok is False:
        assert done.returncode != 0, done.stdout
    return done


def dump(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def make_repo(root: Path) -> tuple:
    repo = root / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    (repo / "gate.sh").write_text('#!/bin/sh\n[ -n "$KEY" ] && [ "$1" = "$KEY" ] && echo allowed && exit 0\necho refused; exit 3\n')
    (repo / "THREAT_MODEL.md").write_text("Callers without the key are untrusted.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "gate: refuse without a key")
    s0 = git(repo, "rev-parse", "HEAD")
    (repo / "gate.sh").write_text('#!/bin/sh\n[ "$1" = "$KEY" ] && echo allowed && exit 0\necho refused; exit 3\n')
    git(repo, "commit", "-qam", "gate: simplify")
    return repo, s0, git(repo, "rev-parse", "HEAD")


class Flow:
    """Drives the scripts through every stage the way the coordinator and its workers would."""

    def __init__(self, tmp: Path):
        self.repo, self.s0, self.s1 = make_repo(tmp)
        self.root = tmp / "campaign"
        self.root.mkdir()
        self.tasks = tmp / "tasks"
        self.n_agents = 0
        dump(self.root / "scope.json", {"changes": [{"id": "change-1", "input": {
            "repository": str(self.repo), "s0": self.s0, "s1": self.s1}}]})
        cli("registry.py", "init", self.root, ok=True)
        out = cli("guidance.py", self.root, "--change", "change-1", "--repo", self.repo, "--commit", self.s1, ok=True)
        self.guidance = out.stdout.strip().splitlines()[-1].split(": ", 1)[1].split()

    def reserve(self, stage, inputs, candidate=None, change="change-1"):
        args = ["reserve", self.root, "--stage", stage, "--change", change]
        if candidate:
            args += ["--candidate", candidate]
        for rel in inputs:
            args += ["--input", rel]
        return json.loads(cli("registry.py", *args, ok=True).stdout)

    def launch(self, aid, agent=None):
        self.n_agents += 1
        agent = agent or f"agent{self.n_agents:04d}xyz"
        call = {"description": f"stage {aid}", "subagent_type": "general-purpose",
                "run_in_background": True, "prompt": "Load the skill ..."}
        (self.root / "runtime").mkdir(exist_ok=True)
        (self.root / f"runtime/{aid}-call.json").write_text(json.dumps(call))
        out = self.tasks / f"{agent}.output"
        out.parent.mkdir(exist_ok=True)
        out.write_text("{}\n")
        (self.root / f"runtime/{aid}-response.txt").write_text(
            f"Async agent launched successfully.\nagentId: {agent} (internal ID)\noutput_file: {out}\n")
        cli("runtime.py", "launch", self.root, aid, "--call", f"runtime/{aid}-call.json",
            "--response", f"runtime/{aid}-response.txt", ok=True)
        return agent

    def start(self, stage, inputs, candidate=None, change="change-1"):
        att = self.reserve(stage, inputs, candidate, change)
        agent = self.launch(att["id"])
        cli("registry.py", "bind", self.root, att["id"], "--agent", agent,
            "--agent-record", f"runtime/{att['id']}-launch.json", ok=True)
        cli("runtime.py", "publish", self.root, att["id"], ok=True)
        att["agent"] = agent
        return att

    def finish(self, att, name, extra, artifacts=(), status="complete", accept=True):
        rel = f"{att['directory']}/{name}"
        rec = {"stage": att["stage"], "agent": att["agent"], "attempt": att["id"], "change": att["change"],
               "status": status, "summary": "done", "security_review": "read the diff",
               "inputs": att["inputs"], "artifacts": list(artifacts)}
        rec.update(extra)
        dump(self.root / rel, rec)
        cli("evidence.py", "seal", self.root, rel, ok=True)
        self.terminate(att)
        if accept:
            cli("registry.py", "accept", self.root, att["id"], rel, ok=True)
        return rel

    def terminate(self, att, status="completed", agent=None):
        note = f"runtime/{att['id']}-notification.txt"
        (self.root / note).write_text(f"task_id: {agent or att['agent']}\nstatus: {status}\n")
        return cli("runtime.py", "terminal", self.root, att["id"], "--notification", note)

    def prepare(self):
        att = self.start("prepare", self.guidance)
        cli("snapshot.py", self.repo, self.s0, self.s1, self.root / att["directory"] / "snapshot", ok=True)
        self.source = f"{att['directory']}/snapshot/source.json"
        self.prepare_rel = self.finish(att, "prepare.json", {"source": self.source},
                                       [f"{att['directory']}/snapshot"])
        return self.prepare_rel

    def hunt(self, keys=("empty-key",)):
        att = self.start("hunt", [self.prepare_rel])
        files = {}
        for key in keys:
            cid = json.loads(cli("registry.py", "candidate", self.root, att["id"], "--agent", att["agent"],
                                 "--key", key, ok=True).stdout)["candidate"]
            rel = f"{att['directory']}/candidates/{cid}.json"
            dump(self.root / rel, {
                "id": cid, "key": key, "change": "change-1", "stage": "hunt", "agent": att["agent"],
                "inputs": [self.prepare_rel], "artifacts": [], "title": "empty key accepted",
                "patch_intent": "simplify", "prior_behavior": "refused", "changed_code": "gate.sh:2",
                "reachable_trigger": "KEY unset, empty argument", "possible_defect": "bypass",
                "false_positive_checks": ["README promise"], "proof_needed": "run both builds"})
            cli("evidence.py", "seal", self.root, rel, ok=True)
            files[cid] = rel
        artifacts = [p for rel in files.values() for p in (rel, rel + ".seal.json")]
        self.hunt_rel = self.finish(att, "hunt.json", {"candidates": list(files), "candidate_files": files},
                                    artifacts)
        self.candidates = files
        return files

    def experiment(self, stage, cid, s0="correct", s1="failure", extra_inputs=(), poc_from=None, accept=True,
                   poc_text="#!/bin/sh\nKEY= sh \"$1/gate.sh\" ''\n"):
        base = [self.prepare_rel, self.hunt_rel, self.candidates[cid], *extra_inputs]
        att = self.start(stage, base, candidate=cid)
        d = att["directory"]
        for state, sha in (("S0", self.s0), ("S1", self.s1)):
            build = self.root / d / "build" / state
            build.mkdir(parents=True)
            (build / "gate.sh").write_text(git(self.repo, "show", f"{sha}:gate.sh") + "\n")
        poc_dir = self.root / d / "poc"
        poc_dir.mkdir()
        if poc_from:
            for name in ("poc.sh", "workload.env"):
                (poc_dir / name).write_bytes((self.root / poc_from / name).read_bytes())
        else:
            (poc_dir / "poc.sh").write_text(poc_text)
            (poc_dir / "workload.env").write_text("KEY=\n")
        (poc_dir / "setup.md").write_text("copy each export into build/, run poc.sh against it\n")
        runs = []
        for state, sha, behavior in (("S0", self.s0, s0), ("S1", self.s1, s1)):
            log = f"{d}/logs/{state}.log"
            (self.root / log).parent.mkdir(parents=True, exist_ok=True)
            (self.root / log).write_text(f"{state}: {'refused' if behavior == 'correct' else 'allowed'}\n")
            runs.append({"state": state, "revision": sha, "deployment": f"{d}/build/{state}/gate.sh",
                         "command": f"sh poc.sh {d}/build/{state}", "log": log, "behavior": behavior})
        rel = self.finish(att, f"{stage}.json", {
            "candidate": cid, "source": self.source, "setup": f"{d}/poc/setup.md", "poc": f"{d}/poc/poc.sh",
            "workload": f"{d}/poc/workload.env", "runs": runs, "build_dirs": [f"{d}/build"]},
            [f"{d}/poc", f"{d}/logs", f"{d}/build"], accept=accept)
        return att, rel

    def decide(self, cid, outcome="REPRODUCED_REGRESSION", repro=None, replay=None, **over):
        inputs = [self.prepare_rel, self.hunt_rel, self.candidates[cid]] + [r for r in (repro, replay) if r]
        att = self.start("adjudicate", inputs, candidate=cid)
        ev = (repro.rsplit("/", 1)[0] + "/logs/S1.log") if repro else self.candidates[cid]
        extra = {"candidate": cid, "outcome": outcome, "reason": "S0 refused, S1 allowed (see logs)",
                 "evidence": [ev]}
        if outcome == "REPRODUCED_REGRESSION":
            checks = {k: {"conclusion": v or "SUPPORTED", "reason": "cited", "evidence": [ev]}
                      for k, v in load("shapes").CHECK_WANT.items()}
            extra.update(reproduction=repro, replay=replay, category="VULNERABILITY", severity="High",
                         likelihood="Medium", severity_reason="operator purge without a key",
                         likelihood_reason="needs the key to be unset", checks=checks)
        extra.update(over)
        return att, self.finish(att, "decision.json", extra)

    def index(self, decisions):
        dump(self.root / "campaign.json", {"title": "Demo hunt", "changes": [{
            "id": "change-1", "input": {"repository": str(self.repo), "s0": self.s0, "s1": self.s1},
            "prepare": self.prepare_rel, "hunt": self.hunt_rel, "limitations": "local shell only",
            "candidates": [{"id": cid, "candidate": rel, "decision": decisions.get(cid)}
                           for cid, rel in self.candidates.items()]}]})

    def full(self, **over):
        self.prepare()
        cid = next(iter(self.hunt()))
        _, repro = self.experiment("reproduce", cid)
        _, replay = self.experiment("replay", cid, extra_inputs=[repro], poc_from=repro.rsplit("/", 1)[0] + "/poc")
        _, dec = self.decide(cid, repro=repro, replay=replay, **over)
        self.index({cid: dec})
        return cid, repro, replay, dec


@pytest.fixture
def flow(tmp_path):
    return Flow(tmp_path)


@pytest.fixture(scope="session")
def mods():
    return {n: load(n) for n in ("rhlib", "evidence", "shapes", "registry", "report", "runtime", "snapshot", "guidance")}
