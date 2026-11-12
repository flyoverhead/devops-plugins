"""Command-line surface: argument errors, scaffold guards, plan rules, the manifest."""
import hashlib
import json

import pytest

from conftest import INTERP, entry, invoke, seven_checks


@pytest.mark.parametrize("words", [
    [],
    ["frobnicate"],
    ["scaffold"],
    ["validate-plan"],
    ["run", "--plan"],
    ["scaffold", "--repo", ".", "--base-ref", "a", "--patched-ref", "b", "--patch-file", "c",
     "--finding-id", "F", "--finding-summary", "S", "--evidence-level", "build", "--output", "o"],
    ["scaffold", "--repo", ".", "--base-ref", "a", "--patched-ref", "b", "--finding-id", "F",
     "--finding-summary", "S", "--evidence-level", "proof", "--output", "o"],
])
def test_bad_invocations_exit_64_quietly(gitenv, words):
    done = invoke(gitenv, *words)
    assert done.returncode == 64
    assert done.stderr.strip() and b"Traceback" not in done.stderr


def test_help(gitenv):
    done = invoke(gitenv, "--help")
    assert done.returncode == 0 and b"validate-plan" in done.stdout


def test_schema_output(gitenv):
    done = invoke(gitenv, "print-schema")
    schema = json.loads(done.stdout)
    assert done.returncode == 0 and "2020-12" in schema["$schema"]
    kinds = schema["properties"]["checks"]["items"]["properties"]["kind"]["enum"]
    assert kinds == ["control", "exploit", "variant", "behavior", "regression", "security", "suite"]


def scaffold_args(p, *, base="pre-fix", fix="HEAD", out=None):
    return ["scaffold", "--repo", p.repo, "--base-ref", base, "--patched-ref", fix, "--finding-id", "Q",
            "--finding-summary", "q", "--evidence-level", "source", "--output", out or p.plan]


def test_scaffold_guards(project):
    p = project()
    p.scaffold()
    again = invoke(p.env, *scaffold_args(p))
    assert again.returncode == 64 and b"never overwritten" in again.stderr
    same = invoke(p.env, *scaffold_args(p, base="HEAD", out=p.root / "same.json"))
    assert same.returncode == 64 and b"identical" in same.stderr
    inside = invoke(p.env, *scaffold_args(p, out=p.repo / "plan.json"))
    assert inside.returncode == 64 and b"outside the repository" in inside.stderr


def test_case_id_comes_from_finding(project):
    p = project()
    p.scaffold()
    assert json.loads(p.plan.read_text())["case_id"] == "UPL-3"


def test_run_will_not_reuse_or_nest_output(project):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    occupied = p.root / "occupied"
    occupied.mkdir()
    (occupied / "earlier.log").write_text("keep me")
    assert invoke(p.env, "run", "--plan", p.plan, "--output", occupied).returncode == 64
    assert (occupied / "earlier.log").read_text() == "keep me"
    assert invoke(p.env, "run", "--plan", p.plan, "--output", p.repo / "ev").returncode == 64
    assert not (p.repo / "ev").exists()


@pytest.mark.parametrize("argv", [
    ["sh", "-c", "id"], ["/bin/bash", "-xc", "id"], ["zsh", "--command", "id"],
    ["env", "-S", "sh -c id"], ["/usr/bin/env", "X=1", "dash", "-ec", "id"], ["python3 -c 0"],
    ["timeout", "5", "sh", "-c", "id"], ["nice", "-n", "5", "bash", "-c", "id"],
    ["xargs", "sh", "-c", "id"], ["busybox", "sh", "-c", "id"], ["nohup", "zsh", "-c", "id"],
    ["stdbuf", "-oL", "dash", "-ec", "id"],
])
def test_command_lines_disguised_as_argv(runner, argv):
    assert runner.shell_hazard(argv)


@pytest.mark.parametrize("argv", [
    ["bash", "checks/go.sh"], ["env", "X=1", INTERP, "t.py"], ["sh", "script.sh", "-c"], ["make", "check"],
    ["timeout", "5", "sh", "checks/run.sh"],
])
def test_real_argv_passes(runner, argv):
    assert runner.shell_hazard(argv) is None


def test_every_kind_required(project):
    p = project()
    p.scaffold()
    p.with_checks([c for c in seven_checks() if c["kind"] != "suite"])
    done = invoke(p.env, "validate-plan", "--plan", p.plan)
    assert done.returncode == 64
    assert any("lacks kinds: suite" in e for e in json.loads(done.stdout)["errors"])
    assert invoke(p.env, "run", "--plan", p.plan, "--output", p.root / "never").returncode == 64


def nth(checks, cid):
    return next(c for c in checks if c["id"] == cid)


@pytest.mark.parametrize("edit,fragment", [
    (lambda cs: nth(cs, "one-level-up")["argv"].append("{side}"), "must not learn the side"),
    (lambda cs: nth(cs, "two-levels-up").update(env={"WHERE": "PPV_SIDE"}), "must not learn the side"),
    (lambda cs: nth(cs, "echo-plain").pop("compare_stream"), "compare_stream belongs"),
    (lambda cs: nth(cs, "baseline-name").update(compare_stream="stderr"), "compare_stream belongs"),
    (lambda cs: nth(cs, "baseline-name").update(cwd="../.."), "stay inside the checkout"),
    (lambda cs: nth(cs, "baseline-name").update(timeout_seconds=0), "whole number of seconds"),
    (lambda cs: nth(cs, "baseline-name").update(colour="red"), "not a known field"),
    (lambda cs: nth(cs, "baseline-name").update(env={"PPV_SCRATCH": "/"}), "reserved or unsafe"),
    (lambda cs: nth(cs, "baseline-name").update(env={"DYLD_LIBRARY_PATH": "/"}), "reserved or unsafe"),
    (lambda cs: nth(cs, "baseline-name").update(covers=[]), "at least one"),
    (lambda cs: cs.append(dict(nth(cs, "baseline-name"))), "each id once"),
])
def test_plan_rule_violations(runner, project, edit, fragment):
    p = project()
    p.scaffold()
    plan = json.loads(p.plan.read_text())
    checks = seven_checks()
    edit(checks)
    plan["checks"] = checks
    problems = runner.plan_errors(plan)
    assert any(fragment in msg for msg in problems), problems


def test_validate_summary_shape(project):
    p = project()
    p.scaffold()
    p.with_checks(seven_checks())
    done = invoke(p.env, "validate-plan", "--plan", p.plan)
    summary = json.loads(done.stdout)
    assert done.returncode == 0 and summary["valid"]
    assert sorted(summary) == ["case_id", "checks", "coverage", "evidence_level", "submodules", "valid"]
    assert summary["coverage"]["exploit"] == 1


def test_plan_with_broken_encoding(project):
    p = project()
    p.scaffold()
    p.plan.write_bytes(b'{"case_id": "\xc3\x28"}')
    done = invoke(p.env, "validate-plan", "--plan", p.plan)
    assert done.returncode == 64 and b"UTF-8" in done.stderr


def test_manifest_covers_all_evidence(project):
    p = project()
    p.scaffold()
    _, out, _ = p.with_checks(seven_checks()).execute()
    listing = json.loads((out / "artifact-manifest.json").read_text())
    assert listing["schema_version"] == "1.0"
    named = {item["path"]: item for item in listing["files"]}
    present = {f.relative_to(out).as_posix() for f in out.rglob("*") if f.is_file()}
    assert set(named) == present - {"artifact-manifest.json"}
    for rel, item in named.items():
        blob = (out / rel).read_bytes()
        assert (item["sha256"], item["bytes"]) == (hashlib.sha256(blob).hexdigest(), len(blob)), rel
    assert {"result.json", "report.md", "patch.diff", "plan.snapshot.json"} <= set(named)
    assert (out / "plan.snapshot.json").read_bytes() == p.plan.read_bytes()


def test_manifest_needs_something_to_list(runner, tmp_path):
    with pytest.raises(runner.Rejected):
        runner.manifest(tmp_path)


def test_manifest_lists_symlinks_without_digest(runner, tmp_path):
    (tmp_path / "real.txt").write_text("r")
    (tmp_path / "link").symlink_to("real.txt")
    runner.manifest(tmp_path)
    listed = {e["path"]: e for e in json.loads((tmp_path / "artifact-manifest.json").read_text())["files"]}
    assert listed["link"] == {"path": "link", "sha256": None, "bytes": None}
    assert listed["real.txt"]["bytes"] == 1


@pytest.mark.parametrize("started,code", [(False, 64), (True, 10)])
def test_unexpected_crash_exit_depends_on_stage(runner, monkeypatch, capsys, started, code):
    def explode(_opts):
        runner.PROGRESS["executing"] = started
        raise RuntimeError("disk vanished")
    monkeypatch.setitem(runner.COMMANDS, "print-schema", (explode, []))
    monkeypatch.setitem(runner.PROGRESS, "executing", False)
    assert runner.main(["print-schema"]) == code
    assert "disk vanished" in capsys.readouterr().err
