#!/usr/bin/env python3
"""Agent bookkeeping under runtime/: launch and terminal records, the handle file, and the worker's wait.

  launch   CAMPAIGN ATTEMPT --call REL --response REL   coordinator, right after the Agent call returns
  terminal CAMPAIGN ATTEMPT --notification REL          coordinator, when the task notification arrives
  publish  CAMPAIGN ATTEMPT                             coordinator, after registry.py bind succeeded
  wait     HANDLE_FILE [--seconds N]                    worker, before its first registry call
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry  # noqa: E402
from rhlib import Refusal, campaign, inside, now, read_json, under, write_json  # noqa: E402

AGENT_ID = re.compile(r"""(?:agentId|agent_id)["']?\s*[:=]\s*["']?([A-Za-z0-9][A-Za-z0-9_-]{5,})""")
TASK_ID = re.compile(r"""task[-_]id["'>]?\s*[:=>]?\s*["']?([A-Za-z0-9][A-Za-z0-9_-]{5,})""")
OUTPUT_FILE = re.compile(r"output_file:\s*(\S+)")
STATUS = re.compile(r"""status["'>]?\s*[:=>]?\s*["']?(completed|failed|killed)\b""")


def raw(root: Path, rel: str) -> str:
    if not inside(rel, registry.RUNTIME):
        raise Refusal(f"raw agent evidence belongs under {registry.RUNTIME}/, not {rel}")
    text = under(root, rel).read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise Refusal(f"{rel} is empty")
    return text


def only(pattern: re.Pattern, text: str, what: str) -> str:
    found = sorted(set(pattern.findall(text)))
    if len(found) != 1:
        raise Refusal(f"expected exactly one {what} in the raw text, found {found or 'none'}")
    return found[0]


def write_once(root: Path, rel: str, data: dict) -> str:
    if (root / rel).exists():
        raise Refusal(f"{rel} already exists; runtime records are never rewritten")
    write_json(root / rel, data)
    return rel


def cmd_launch(root: Path, args) -> dict:
    call_text = raw(root, args.call)
    try:
        call = json.loads(call_text)
    except json.JSONDecodeError as exc:
        raise Refusal(f"{args.call} must hold the Agent call input as JSON ({exc})") from None
    if not isinstance(call, dict):
        raise Refusal(f"{args.call} must hold a JSON object")
    response = raw(root, args.response)
    agent = only(AGENT_ID, response, "agent id")
    output = Path(only(OUTPUT_FILE, response, "output_file path"))
    if output.name != f"{agent}.output":
        raise Refusal(f"output_file {output} is not named {agent}.output; the launch text was not "
                      "copied from the Agent tool result")
    try:
        present = output.is_file()
    except PermissionError:
        present = None
    if present is False:
        raise Refusal(f"output_file {output} does not exist; the launch text was not copied from the "
                      "Agent tool result")
    if present is None:
        print(f"runtime.py launch: {output} cannot be inspected from this sandbox; only its name was checked",
              file=sys.stderr)
    rel = write_once(root, f"{registry.RUNTIME}/{args.attempt}-launch.json", {
        "event": "launch", "attempt": args.attempt, "tool": "claude.Agent", "call": call,
        "response": {"agent_id": agent}, "observed_at": now(), "evidence": [args.call, args.response]})
    return {"record": rel, "agent": agent}


def cmd_terminal(root: Path, args) -> dict:
    text = raw(root, args.notification)
    response = {"task_id": only(TASK_ID, text, "task id"), "status": only(STATUS, text, "status")}
    att = registry.attempt_of(registry.load(root), args.attempt)
    agent = registry.launched_agent(root, att)
    if response["task_id"] != agent:
        raise Refusal(f"the notification names {response['task_id']}, but {args.attempt} was launched as {agent!r}")
    rel = write_once(root, f"{registry.RUNTIME}/{args.attempt}-terminal.json", {
        "event": "terminal", "attempt": args.attempt, "tool": "claude.task_notification",
        "response": response, "observed_at": now(), "evidence": [args.notification]})
    return {"record": rel, **response}


def cmd_publish(root: Path, args) -> dict:
    att = registry.attempt_of(registry.load(root), args.attempt)
    if att["state"] != "running" or not att["agent"]:
        raise Refusal(f"{args.attempt} is not bound; run registry.py bind first")
    rel = f"{registry.RUNTIME}/{args.attempt}-handle"
    if (root / rel).exists():
        if (root / rel).read_text() != att["agent"]:
            raise Refusal(f"{rel} already names another agent")
    else:
        (root / rel).write_text(att["agent"])
    return {"handle": rel, "agent": att["agent"]}


def cmd_wait(args) -> int:
    path = Path(args.handle)
    if not re.fullmatch(r"a\d{3,}-handle", path.name) or path.parent.name != registry.RUNTIME:
        print(f"runtime.py wait: {path} is not a runtime/<attempt>-handle file", file=sys.stderr)
        return 2
    deadline = time.monotonic() + args.seconds
    while True:
        if path.is_file() and not path.is_symlink():
            handle = path.read_text().strip()
            if handle:
                print(handle)
                return 0
        if time.monotonic() >= deadline:
            print(f"runtime.py wait: no handle at {path} after {args.seconds}s; stop as blocked", file=sys.stderr)
            return 1
        time.sleep(args.every)


def main(argv=None) -> int:
    top = argparse.ArgumentParser(prog="runtime.py", description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest="command", required=True)
    p = sub.add_parser("launch")
    p.add_argument("campaign")
    p.add_argument("attempt")
    p.add_argument("--call", required=True)
    p.add_argument("--response", required=True)
    p = sub.add_parser("terminal")
    p.add_argument("campaign")
    p.add_argument("attempt")
    p.add_argument("--notification", required=True)
    p = sub.add_parser("publish")
    p.add_argument("campaign")
    p.add_argument("attempt")
    p = sub.add_parser("wait")
    p.add_argument("handle")
    p.add_argument("--seconds", type=float, default=120.0)
    p.add_argument("--every", type=float, default=2.0)
    args = top.parse_args(argv)
    if args.command == "wait":
        return cmd_wait(args)
    try:
        root = campaign(args.campaign)
        if not re.fullmatch(r"a\d{3,}", args.attempt):
            raise Refusal(f"{args.attempt} is not an attempt id")
        with registry.locked(root):
            out = {"launch": cmd_launch, "terminal": cmd_terminal, "publish": cmd_publish}[args.command](root, args)
    except (Refusal, OSError) as exc:
        print(f"runtime.py {args.command} refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
