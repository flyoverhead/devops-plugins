import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "evals" / "check_contamination.py"
SECRET = "The kiosk writer must refuse a key that climbs out of the cache directory."


def run(*args):
    res = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


@pytest.fixture
def suite(tmp_path):
    root = tmp_path / "plug"
    graders = root / "evals" / "outcome-kiosk" / "graders"
    graders.mkdir(parents=True)
    (root / "evals" / "outcome-kiosk" / "case.yaml").write_text("name: outcome-kiosk\n")
    (graders / "kiosk-verdict.md").write_text(f"---\ntype: llm\n---\n\n{SECRET}\nshort line\n")
    (graders / "no-edit.md").write_text("---\ntype: tool_used\ntool: Edit\n---\n")
    return root


def result(tmp_path, suite, runs, shape="arms"):
    case = {"name": "outcome-kiosk"}
    if shape == "arms":
        case["arms"] = {"with": runs, "without": []}
    else:
        case["runs"] = runs
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"suite": {"root": str(suite)}, "cases": [case]}))
    return path


def trace(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def judged(text="judge votes: PASS PASS PASS"):
    return [{"name": "kiosk-verdict", "explanation": text}]


def test_clean_runs_pass(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t1", "read disk.go, ran go vet"), "graders": judged()},
            {"tracePath": trace(tmp_path, "t2", "nothing special"), "graders": judged()}]
    code, out, _ = run(result(tmp_path, suite, runs))
    assert code == 0 and out.strip() == "ok: 2 run(s) clean"


def test_bare_runs_shape(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t", "fine"), "graders": []}]
    code, out, _ = run(result(tmp_path, suite, runs, shape="runs"))
    assert code == 0 and "ok: 1 run(s) clean" in out


def test_grader_body_in_trace(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t", f"cat said: {SECRET}"), "graders": judged()}]
    code, out, _ = run(result(tmp_path, suite, runs))
    assert code == 1
    assert out.startswith("LEAK outcome-kiosk/with#1 via agent log -> ") and SECRET in out


def test_pass_phrase_in_trace(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t", "PASS only if the ledger"), "graders": []}]
    assert run(result(tmp_path, suite, runs))[0] == 1


def test_slug_in_trace(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t", "opened kiosk-verdict.md"), "graders": []}]
    code, out, _ = run(result(tmp_path, suite, runs))
    assert code == 1 and "kiosk-verdict.md" in out


def test_eval_path_in_trace_and_allow_listing(tmp_path, suite):
    text = f"Glob -> {suite.as_posix()}/evals/outcome-kiosk/case.yaml"
    runs = [{"tracePath": trace(tmp_path, "t", text), "graders": []}]
    res = result(tmp_path, suite, runs)
    code, out, _ = run(res)
    assert code == 1 and "/evals/" in out
    assert run(res, "--allow-listing")[0] == 0


def test_relative_case_path_in_trace(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t", "ls evals/outcome-kiosk/"), "graders": []}]
    res = result(tmp_path, suite, runs)
    assert run(res)[0] == 1 and run(res, "--allow-listing")[0] == 0


def test_trace_directory(tmp_path, suite):
    tdir = tmp_path / "keep"
    (tdir / "sub").mkdir(parents=True)
    (tdir / "a.jsonl").write_text("plain\n")
    (tdir / "sub" / "b.jsonl").write_text(SECRET)
    runs = [{"tracePath": str(tdir), "graders": []}]
    assert run(result(tmp_path, suite, runs))[0] == 1


def test_judge_restating_body_is_not_a_leak(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t", "fine"), "graders": judged(f"Judge: {SECRET}")}]
    assert run(result(tmp_path, suite, runs))[0] == 0


def test_judge_naming_eval_path_is_a_leak(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t", "fine"),
             "graders": judged("see evals/outcome-kiosk/graders/kiosk-verdict.md")}]
    code, out, _ = run(result(tmp_path, suite, runs))
    assert code == 1 and "via judge verdict -> " in out


def test_judge_only_warns(tmp_path, suite):
    runs = [{"graders": judged()}]
    code, out, err = run(result(tmp_path, suite, runs))
    assert code == 0 and "ok: 1 run(s) clean" in out
    assert "only judge text" in err


def test_missing_trace_file_counts_as_unreadable(tmp_path, suite):
    runs = [{"tracePath": str(tmp_path / "gone.jsonl"), "graders": judged()}]
    code, _, err = run(result(tmp_path, suite, runs))
    assert code == 0 and "1 of 1" in err


@pytest.mark.parametrize("payload", [{"cases": []}, {}, [], {"cases": [{"name": "x", "arms": {"with": []}}]},
                                     {"cases": [{"name": "x", "runs": [{"graders": []}]}]}])
def test_empty_input_fails(tmp_path, suite, payload):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(payload))
    code, _, err = run(path, "--suite", suite)
    assert code == 1 and "nothing to check" in err


def test_no_graders_loaded_fails(tmp_path, suite):
    runs = [{"tracePath": trace(tmp_path, "t", "fine"), "graders": judged()}]
    res = result(tmp_path, suite, runs)
    assert run(res)[0] == 0
    code, _, err = run(res, "--suite", tmp_path / "empty-suite")
    assert code == 1 and "no grader files" in err


def test_garbage_json_fails(tmp_path):
    path = tmp_path / "r.json"
    path.write_text("{not json")
    assert run(path)[0] == 1


@pytest.mark.parametrize("argv", [[], ["--bogus"], ["/no/such/result.json"]])
def test_bad_usage(argv):
    assert run(*argv)[0] == 2


def test_suite_flag_overrides_result(tmp_path, suite):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"suite": {"root": "/nowhere"}, "cases": [
        {"name": "outcome-kiosk", "runs": [{"tracePath": trace(tmp_path, "t", SECRET)}]}]}))
    code, _, err = run(path)
    assert code == 1 and "no grader files under /nowhere" in err
    code, out, _ = run(path, "--suite", suite)
    assert code == 1 and "via agent log" in out


def test_real_suite_markers_load():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import check_contamination as cc
    finally:
        sys.path.pop(0)
    markers = cc.build_markers(SCRIPT.resolve().parent.parent)
    assert "halt-report.md" in markers["slug"]
    assert any(p.endswith("evals/outcome-reviewer-unavailable/") for p in markers["path"])


def test_stdlib_only():
    allowed = {"argparse", "json", "sys", "pathlib"}
    imported = {line.split()[1].split(".")[0] for line in SCRIPT.read_text().splitlines()
                if line.startswith(("import ", "from "))}
    assert imported <= allowed, imported - allowed
