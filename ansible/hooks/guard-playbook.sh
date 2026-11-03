#!/usr/bin/env bash
set -uo pipefail

read -r -d '' analyzer <<'PY'
import json
import os
import re
import sys

SAFE_LONG = {"--check", "--syntax-check", "--list-tasks", "--list-hosts", "--list-tags"}
LONG_WITH_VALUE = {
    "--tags", "--skip-tags", "--limit", "--inventory", "--extra-vars", "--user", "--private-key",
    "--forks", "--vault-id", "--vault-password-file", "--start-at-task", "--connection", "--timeout",
    "--module-path", "--become-user", "--become-method",
}
SHORT_WITH_VALUE =set("eilutTcfMBP")
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "time"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")
REDIR = re.compile(r"^[0-9]*(>>?|<|>&|&>)$")
REDIR_ATTACHED = re.compile(r"^[0-9]*(>>?|<|>&|&>)")
PLACEHOLDER = "\0"


def find_close(s, i):
    depth = 1
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            j = s.find("'", i + 1)
            i = len(s) if j < 0 else j + 1
            continue
        if c == '"':
            i += 1
            while i < len(s) and s[i] != '"':
                i += 2 if s[i] == "\\" else 1
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(s)


def find_backtick(s, i):
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == "`":
            return i
        i += 1
    return len(s)


def split(s, out):
    words = []
    cur = None
    i = 0
    n = len(s)

    def push():
        nonlocal cur
        if cur is not None:
            words.append(cur)
            cur = None

    def end():
        nonlocal words
        push()
        if words:
            out.append(words)
            words = []

    def add(text):
        nonlocal cur
        cur = (cur or "") + text

    while i < n:
        c = s[i]
        if c == "\\":
            if i + 1 < n and s[i + 1] != "\n":
                add(s[i + 1])
            i += 2
        elif c == "'":
            j = s.find("'", i + 1)
            j = n if j < 0 else j
            add(s[i + 1:j])
            i = j + 1
        elif c == '"':
            i += 1
            add("")
            while i < n and s[i] != '"':
                if s[i] == "\\" and i + 1 < n:
                    add(s[i + 1])
                    i += 2
                elif s.startswith("$(", i):
                    j = find_close(s, i + 2)
                    split(s[i + 2:j], out)
                    add(PLACEHOLDER)
                    i = j + 1
                elif s[i] == "`":
                    j = find_backtick(s, i + 1)
                    split(s[i + 1:j], out)
                    add(PLACEHOLDER)
                    i = j + 1
                else:
                    add(s[i])
                    i += 1
            i += 1
        elif s.startswith("$(", i):
            j = find_close(s, i + 2)
            split(s[i + 2:j], out)
            add(PLACEHOLDER)
            i = j + 1
        elif c == "`":
            j = find_backtick(s, i + 1)
            split(s[i + 1:j], out)
            add(PLACEHOLDER)
            i = j + 1
        elif c == "#" and cur is None:
            while i < n and s[i] != "\n":
                i += 1
        elif c in " \t":
            push()
            i += 1
        elif c in "\n;|()":
            end()
            i += 1
        elif c == "&":
            prev = s[i - 1] if i else ""
            nxt = s[i + 1] if i + 1 < n else ""
            if prev in "<>" or nxt == ">":
                add(c)
            else:
                end()
            i += 1
        else:
            add(c)
            i += 1
    end()


def skip_options(words, i, with_value):
    while i < len(words):
        w = words[i]
        if w == "--":
            return i + 1
        if not w.startswith("-") or w == "-":
            break
        i += 2 if w in with_value else 1
    return i


def prefix(words):
    i = 0
    while i < len(words):
        w = words[i]
        if w in KEYWORDS or ASSIGN.match(w):
            i += 1
        elif REDIR.match(w):
            i += 2
        elif REDIR_ATTACHED.match(w):
            i += 1
        else:
            break
    return words[i:]


def classify(words, depth=0):
    words = prefix(words)
    if not words or depth > 8:
        return None
    name = os.path.basename(words[0])
    rest = words[1:]
    if name == "ansible-playbook":
        return ("play", rest)
    if name in ("sudo", "doas"):
        return classify(rest[skip_options(rest, 0, {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"}):], depth + 1)
    if name == "env":
        return classify(rest[skip_options(rest, 0, {"-u", "-C", "-S", "-P"}):], depth + 1)
    if name in ("nohup", "exec", "command", "builtin", "setsid", "stdbuf", "ionice", "chrt"):
        return classify(rest[skip_options(rest, 0, {"-n", "-c", "-p", "-i", "-o", "-e"}):], depth + 1)
    if name == "nice":
        return classify(rest[skip_options(rest, 0, {"-n", "--adjustment"}):], depth + 1)
    if name == "timeout":
        j = skip_options(rest, 0, {"-s", "-k", "--signal", "--kill-after"})
        return classify(rest[j + 1:], depth + 1)
    if name == "xargs":
        return classify(rest[skip_options(rest, 0, {"-I", "-n", "-P", "-L", "-s", "-d", "-E", "-a"}):], depth + 1)
    if name == "find":
        for k, w in enumerate(rest):
            if w in ("-exec", "-execdir", "-ok", "-okdir"):
                return classify(rest[k + 1:], depth + 1)
        return None
    if name in ("uv", "poetry", "pipx", "pipenv", "uvx"):
        j = 0
        if name != "uvx":
            while j < len(rest) and rest[j] in ("tool",):
                j += 1
            if j >= len(rest) or rest[j] != "run":
                return None
            j += 1
        j = skip_options(rest, j, {"--with", "--python", "-p", "--project", "--directory", "--env-file",
                                   "--group", "--extra", "--spec", "--from", "--index", "-w", "-e"})
        return classify(rest[j:], depth + 1)
    if name in SHELLS:
        k = 0
        while k < len(rest):
            w = rest[k]
            if w in ("-o", "+o", "-O", "+O"):
                k += 2
                continue
            if w.startswith("-") and not w.startswith("--") and "c" in w[1:]:
                for cand in rest[k + 1:]:
                    if not cand.startswith("-"):
                        return ("sh", cand)
                return None
            if w.startswith("-"):
                k += 1
                continue
            return None
        return None
    if name == "su":
        for k, w in enumerate(rest):
            if w == "--command" or (w.startswith("-") and not w.startswith("--") and "c" in w[1:]):
                if k + 1 < len(rest):
                    return ("sh", rest[k + 1])
                return None
        return None
    if name == "eval":
        return ("sh", " ".join(rest))
    return None


def is_safe(args):
    k = 0
    while k < len(args):
        a = args[k]
        if a == "--":
            break
        if a in SAFE_LONG:
            return True
        if a.startswith("--"):
            k += 2 if a in LONG_WITH_VALUE else 1
            continue
        if a.startswith("-") and len(a) > 1:
            for pos, ch in enumerate(a[1:], 1):
                if ch == "C":
                    return True
                if ch in SHORT_WITH_VALUE:
                    if pos == len(a) - 1:
                        k += 1
                    break
        k += 1
    return False


def violates(command, depth=0):
    if depth > 6:
        return False
    cmds = []
    split(command, cmds)
    for words in cmds:
        hit = classify(words)
        if hit is None:
            continue
        kind, payload = hit
        if kind == "play":
            if not is_safe(payload):
                return True
        elif violates(payload, depth + 1):
            return True
    return False


def main():
    mode = sys.argv[1]
    data = sys.stdin.read()
    if mode == "json":
        try:
            data = json.loads(data).get("tool_input", {}).get("command", "") or ""
        except (ValueError, AttributeError):
            return 0
    return 3 if violates(data) else 0


sys.exit(main())
PY

input=$(cat)
mode=raw
if command -v jq >/dev/null 2>&1; then
  command_line=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
  payload=$command_line
elif command -v python3 >/dev/null 2>&1; then
  mode=json
  payload=$input
else
  echo "guard-playbook: neither jq nor python3 found, playbook guard skipped." >&2
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "guard-playbook: python3 not found, playbook guard skipped." >&2
  exit 0
fi

printf '%s' "$payload" | python3 -c "$analyzer" "$mode"
rc=$?

if [ "$rc" -eq 3 ]; then
  echo "Blocked: run ansible-playbook against real hosts yourself; Claude may use --check, --syntax-check or --list-*." >&2
  exit 2
fi
if [ "$rc" -ne 0 ]; then
  echo "guard-playbook: analyzer failed (exit $rc), playbook guard skipped." >&2
fi
exit 0
