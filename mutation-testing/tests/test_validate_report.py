import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
SMOKE = HERE / "smoke-test.sh"
VALIDATOR = HERE / "validate_report.py"

sys.path.insert(0, str(HERE))
import validate_report as vr  # noqa: E402


def run_cli(*args):
    return subprocess.run([sys.executable, str(VALIDATOR), *map(str, args)],
                          capture_output=True, text=True)


def test_reference_report_passes_every_check():
    assert vr.check((FIX / "report-correct.md").read_text()) == []


def test_ge_zero_marked_equivalent_fails():
    problems = vr.check((FIX / "report-both-equivalent.md").read_text())
    assert len(problems) == 1 and "`>= 0` on line 42 is listed as equivalent" in problems[0]


def test_ne_zero_left_out_of_equivalents_fails():
    problems = vr.check((FIX / "report-none-equivalent.md").read_text())
    assert any("`!= 0` on line 42 is not listed as equivalent" in p for p in problems)


def test_prose_only_is_not_a_report():
    with pytest.raises(vr.ReportError, match="no section headings"):
        vr.check("All nine mutants were looked at and most of them matter. " * 20)


def test_report_lacking_equivalence_table_is_refused():
    text = (FIX / "report-correct.md").read_text().replace("## Equivalent Mutants", "## Notes")
    with pytest.raises(vr.ReportError, match="section about equivalent mutants"):
        vr.check(text)


def test_merged_boundary_row_fails():
    merged = ("| 1 | `src/lib.rs` | 42 | `rides_left > 0` → `!= 0` and `>= 0` | both agree on u32; "
              "judged equivalent |")
    text = (FIX / "report-correct.md").read_text()
    text = re.sub(r"^\| 1 \| `src/lib.rs` \| 42 \|.*$", lambda _: merged, text, count=1, flags=re.M)
    assert merged in text
    assert any("`>= 0` on line 42 is listed as equivalent" in p for p in vr.check(text))


def test_ge_zero_in_reason_cell_only_is_fine():
    text = (FIX / "report-correct.md").read_text().replace(
        "agree on every value |", "agree on every value, unlike `>= 0` |")
    assert vr.check(text) == []


def test_split_original_and_mutated_columns():
    text = (FIX / "report-correct.md").read_text().replace(
        "| # | File | Line | Original → Mutated | Reason |\n|---|---|---|---|---|\n"
        "| 1 | `src/lib.rs` | 42 | `rides_left > 0` → `rides_left != 0` |",
        "| # | File | Line | Original | Mutated | Reason |\n|---|---|---|---|---|---|\n"
        "| 1 | `src/lib.rs` | 42 | `rides_left > 0` | `rides_left != 0` |")
    assert "| Original | Mutated |" in text
    assert vr.check(text) == []


def test_not_equivalent_heading_is_not_an_equivalence_section():
    text = (FIX / "report-correct.md").read_text().replace(
        "## Tier 2: High", "## Not equivalent: boundary\n\n| Mutation |\n|---|\n| `>= 0` |\n\n## Tier 2: High")
    assert vr.check(text) == []
    assert [t for t, _, _ in vr.sections(text) if vr.is_equivalent_heading(t)] == ["Equivalent Mutants"]


def test_equivalent_span_does_not_swallow_identical_text_elsewhere():
    text = (FIX / "report-correct.md").read_text()
    row = next(ln for ln in text.splitlines() if ln.startswith("| 1 | `src/lib.rs` | 42 |"))
    text = text.replace("## Recommendations", f"## Recommendations\n\n{row}\n", 1)
    text = text.replace("`rides_left > 0` → `rides_left >= 0` (COS)", "`rides_left > 0` → `rides_left ≥ 0` (COS)")
    text = text.replace("`>= 0` on `u32` is always true", "the mutant is always true")
    problems = vr.check(text)
    assert any("never discussed as a real gap" in p for p in problems)


def test_hash_lines_in_fences_do_not_count():
    with pytest.raises(vr.ReportError, match="no section headings"):
        vr.check("```sh\n# Equivalent mutants\n```\n" + "plain prose " * 60)


def test_counter_finding_under_tier_one_fails():
    text = (FIX / "report-correct.md").read_text().replace(
        "## Tier 2: High", "### C-3: counter\n\n- **Location:** `src/lib.rs`, line 36, `gate.served`\n\n## Tier 2: High")
    problems = vr.check(text)
    assert any("`served`" in p for p in problems)
    assert any("Tier 1 cites line 36" in p for p in problems)


def test_dropping_a_survivor_line_fails():
    text = (FIX / "report-correct.md").read_text().replace("line 47", "the queue line")
    assert any("line 47 is never cited" in p for p in vr.check(text))


@pytest.mark.parametrize("snippet,line,hit", [
    ("Line 23", 23, True), ("lines 23 and 25", 25, True), ("lines: 32, 33", 33, True),
    ("| 42 |", 42, True), ("`src/lib.rs:47`", 47, True), ("line 230", 23, False), ("byte 23", 23, False),
])
def test_citation_shapes(snippet, line, hit):
    assert vr.cites_line(snippet, line) is hit


def test_command_line_status_codes(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("")
    stub = tmp_path / "stub.md"
    stub.write_text("# Report\n\n## Equivalent Mutants\n\n| # | Mutation |\n|---|---|\n| 1 | `!= 0` |\n")
    assert run_cli(empty).returncode == 1
    out = run_cli(stub)
    assert out.returncode == 1 and "stub" in out.stderr
    assert run_cli(tmp_path / "absent.md").returncode == 2
    good = run_cli(FIX / "report-correct.md")
    assert good.returncode == 0 and good.stdout.startswith("valid: ") and "report-correct.md" in good.stdout
    teeth = run_cli("--expect-fail", FIX / "report-correct.md")
    assert teeth.returncode == 1 and "no teeth" in teeth.stderr
    rejected = run_cli("--expect-fail", FIX / "report-both-equivalent.md")
    assert rejected.returncode == 0 and "listed as equivalent" in rejected.stdout


def test_smoke_without_model():
    out = subprocess.run(["bash", str(SMOKE)], env={**os.environ, "DETERMINISTIC_ONLY": "yes"},
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "validator self-test passed" in out.stdout


FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, shutil, sys
args = sys.argv[1:]
out = args[args.index("--json") + 1]
mode = os.environ["FAKE_MODE"]
run_root = os.path.join(os.environ["TMPDIR"], "e-run")
work = os.path.join(run_root, "tmp", "claude-501", "mutation-testing-cwd-1")
os.makedirs(work, exist_ok=True)
if mode in ("good", "bad"):
    src = "report-correct.md" if mode == "good" else "report-both-equivalent.md"
    shutil.copy(os.path.join(os.environ["FIXTURES"], src), os.path.join(work, "mutation-testing-report.md"))
trace = os.path.join(run_root, "out", "trace.jsonl")
if mode in ("kept", "kept-base"):
    base = os.environ["CALLER_TMP"] if mode == "kept" else os.environ.get(
        "SMOKE_RUN_ROOT_BASE_FAKE", os.environ.get("SMOKE_RUN_ROOT_BASE", ""))
    root = os.path.join(base, "e-Kept42")
    report_dir = os.path.join(root, "sealed", "tmp", "claude-501", "mutation-testing-cwd-1")
    os.makedirs(report_dir)
    shutil.copy(os.path.join(os.environ["FIXTURES"], "report-correct.md"), os.path.join(report_dir, "mutation-testing-report.md"))
    os.chmod(os.path.join(root, "sealed"), 0)
    trace = os.path.join(root, "out", "trace.jsonl")
run = {"score": 0.5 if mode == "low" else 1, "tracePath": trace}
cases = [] if mode == "empty" else [{"name": "outcome-weak-suite-analysis", "arms": {"with": [run]}}]
json.dump({"partial": mode == "partial", "cases": cases}, open(out, "w"))
'''


@pytest.fixture
def fake_env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    stray = tmp_path / "elsewhere"
    stray.mkdir()
    shutil.copy(FIX / "report-correct.md", stray / "mutation-testing-report.md")
    return {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "TMPDIR": str(tmp),
            "ANTHROPIC_API_KEY": "test-only", "FIXTURES": str(FIX), "CALLER_TMP": str(tmp.resolve())}


@pytest.mark.parametrize("mode,rc,needle", [
    ("good", 0, "all checks passed, 1 report"),
    ("missing", 1, "the run left no report"),
    ("bad", 1, "validator rejected"),
    ("partial", 1, "partial run"),
    ("empty", 1, "no cases ran"),
    ("low", 1, "score below 1"),
])
def test_smoke_with_stub_cli(fake_env, mode, rc, needle):
    out = subprocess.run(["bash", str(SMOKE)], env={**fake_env, "FAKE_MODE": mode},
                         capture_output=True, text=True)
    assert out.returncode == rc, out.stdout + out.stderr
    assert needle in out.stdout + out.stderr


def test_smoke_finds_kept_run_dir_from_trace_path(fake_env):
    out = subprocess.run(["bash", str(SMOKE)], env={**fake_env, "FAKE_MODE": "kept"},
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "1 report(s) validated" in out.stdout
    assert not (Path(fake_env["CALLER_TMP"]) / "e-Kept42").exists()


def test_smoke_finds_kept_run_dir_under_run_root_base(fake_env, tmp_path):
    base = tmp_path / "evalroot"
    base.mkdir()
    env = {**fake_env, "FAKE_MODE": "kept-base", "SMOKE_RUN_ROOT_BASE": str(base)}
    out = subprocess.run(["bash", str(SMOKE)], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "1 report(s) validated" in out.stdout
    assert not (base / "e-Kept42").exists()


def test_smoke_ignores_run_dir_outside_known_bases(fake_env, tmp_path):
    base = tmp_path / "evalroot"
    base.mkdir()
    env = {**fake_env, "FAKE_MODE": "kept-base", "SMOKE_RUN_ROOT_BASE": str(base)}
    env["SMOKE_RUN_ROOT_BASE"] = str(tmp_path / "elsewhere")
    env_fake = {**env, "SMOKE_RUN_ROOT_BASE_FAKE": str(base)}
    out = subprocess.run(["bash", str(SMOKE)], env=env_fake, capture_output=True, text=True)
    assert out.returncode == 1 and "left no report" in out.stderr
    (base / "e-Kept42" / "sealed").chmod(0o700)


def test_smoke_skips_without_key(fake_env):
    env = {k: v for k, v in fake_env.items() if k != "ANTHROPIC_API_KEY"}
    out = subprocess.run(["bash", str(SMOKE)], env={**env, "FAKE_MODE": "good"},
                         capture_output=True, text=True)
    assert out.returncode == 2 and "not run" in out.stdout


def test_smoke_cleans_up_only_after_success(fake_env):
    tmp = Path(fake_env["TMPDIR"])
    subprocess.run(["bash", str(SMOKE)], env={**fake_env, "FAKE_MODE": "good"}, capture_output=True)
    assert not list(tmp.glob("mutation-smoke.*"))
    subprocess.run(["bash", str(SMOKE)], env={**fake_env, "FAKE_MODE": "bad"}, capture_output=True)
    assert len(list(tmp.glob("mutation-smoke.*"))) == 1
