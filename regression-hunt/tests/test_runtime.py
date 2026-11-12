"""runtime.py: launch and terminal records, handle publishing, the worker wait."""
import json
import threading
import time

from conftest import cli


def test_launch_record_written_once(flow):
    att = flow.reserve("prepare", flow.guidance)
    agent = flow.launch(att["id"])
    rec = json.loads((flow.root / f"runtime/{att['id']}-launch.json").read_text())
    assert rec["event"] == "launch" and rec["tool"] == "claude.Agent"
    assert rec["response"] == {"agent_id": agent} and rec["call"]["subagent_type"] == "general-purpose"
    assert rec["evidence"] == [f"runtime/{att['id']}-call.json", f"runtime/{att['id']}-response.txt"]
    again = cli("runtime.py", "launch", flow.root, att["id"], "--call", f"runtime/{att['id']}-call.json",
                "--response", f"runtime/{att['id']}-response.txt", ok=False)
    assert "never rewritten" in again.stderr


def test_launch_needs_one_agent_id(flow):
    (flow.root / "runtime").mkdir()
    (flow.root / "runtime/c.json").write_text('{"subagent_type": "general-purpose"}')
    (flow.root / "runtime/r.txt").write_text("agentId: aaaaaaa1\nagentId: bbbbbbb2\n")
    assert "exactly one" in cli("runtime.py", "launch", flow.root, "a001", "--call", "runtime/c.json",
                                "--response", "runtime/r.txt", ok=False).stderr
    (flow.root / "loose.txt").write_text("agentId: aaaaaaa1")
    assert "under runtime/" in cli("runtime.py", "launch", flow.root, "a001", "--call", "runtime/c.json",
                                   "--response", "loose.txt", ok=False).stderr


def test_publish_only_after_bind(flow):
    att = flow.reserve("prepare", flow.guidance)
    assert "not bound" in cli("runtime.py", "publish", flow.root, att["id"], ok=False).stderr
    started = flow.start("prepare", flow.guidance)
    assert (flow.root / f"runtime/{started['id']}-handle").read_text() == started["agent"]


def test_wait_sees_late_handle(tmp_path):
    handle = tmp_path / "runtime" / "a004-handle"
    handle.parent.mkdir()
    threading.Timer(0.5, lambda: handle.write_text("agent-late01")).start()
    t = time.monotonic()
    done = cli("runtime.py", "wait", handle, "--seconds", "10", "--every", "0.2", ok=True)
    assert done.stdout.strip() == "agent-late01" and time.monotonic() - t < 8


def test_wait_times_out_and_checks_name(tmp_path):
    (tmp_path / "runtime").mkdir()
    done = cli("runtime.py", "wait", tmp_path / "runtime/a001-handle", "--seconds", "0.3", "--every", "0.1")
    assert done.returncode == 1 and "blocked" in done.stderr
    assert cli("runtime.py", "wait", tmp_path / "other.txt").returncode == 2


def test_launch_needs_the_real_output_file(flow):
    att = flow.reserve("prepare", flow.guidance)
    (flow.root / "runtime").mkdir()
    (flow.root / "runtime/c.json").write_text('{"subagent_type": "general-purpose"}')
    for text in ("agentId: abcdef123\n", "agentId: abcdef123\noutput_file: /nonexistent/abcdef123.output\n",
                 f"agentId: abcdef123\noutput_file: {flow.root / 'scope.json'}\n"):
        (flow.root / "runtime/r.txt").write_text(text)
        done = cli("runtime.py", "launch", flow.root, att["id"], "--call", "runtime/c.json", "--response", "runtime/r.txt")
        assert done.returncode == 1, text
    assert not (flow.root / f"runtime/{att['id']}-launch.json").exists()


def test_terminal_refuses_other_task(flow):
    att = flow.start("prepare", flow.guidance)
    done = flow.terminate(att, agent="someoneelse9")
    assert done.returncode == 1 and "was launched as" in done.stderr
    assert not (flow.root / f"runtime/{att['id']}-terminal.json").exists()


def test_launch_tolerates_unreadable_task_dir(flow, mods, monkeypatch, capsys):
    runtime = mods["runtime"]
    att = flow.reserve("prepare", flow.guidance)
    (flow.root / "runtime").mkdir()
    (flow.root / "runtime/c.json").write_text('{"subagent_type": "general-purpose"}')
    (flow.root / "runtime/r.txt").write_text("agentId: abcdef123\noutput_file: /sealed/tasks/abcdef123.output\n")

    def denied(self):
        raise PermissionError("Operation not permitted")
    monkeypatch.setattr(runtime.Path, "is_file", denied)
    assert runtime.main(["launch", str(flow.root), att["id"], "--call", "runtime/c.json", "--response", "runtime/r.txt"]) == 0
    assert "only its name was checked" in capsys.readouterr().err
