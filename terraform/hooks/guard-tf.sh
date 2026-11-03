#!/usr/bin/env bash
set -u

if ! command -v jq >/dev/null 2>&1; then
  echo "guard-tf: jq not found, the terraform guard is inactive" >&2
  exit 0
fi

command=$(jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -n "$command" ] || exit 0

case "$command" in
  *terraform* | *tofu*) ;;
  *) exit 0 ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "guard-tf: python3 not found, the terraform guard is inactive" >&2
  exit 0
fi

exec python3 - "$command" <<'PY'
import os
import re
import sys

TF_NAMES = {"terraform", "tofu"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "time"}
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
BLOCKED = {"apply", "destroy", "import", "taint", "untaint", "force-unlock", "refresh"}
BLOCKED_STATE = {"mv", "rm", "push", "replace-provider"}
SUDO_ARG = {"-u", "-g", "-h", "-p", "-C", "-r", "-t", "-U", "-D", "-R", "-T"}
TIMEOUT_ARG = {"-s", "--signal", "-k", "--kill-after"}
ENV_ARG = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
XARGS_ARG = {"-I", "-n", "-L", "-P", "-s", "-d", "-E", "-a", "-l", "-e",
             "--max-args", "--max-procs", "--delimiter", "--arg-file",
             "--max-lines", "--max-chars", "--eof"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
MAX_DEPTH = 8


class Seg:
    def __init__(self):
        self.words = []
        self.docs = []


def close_paren(s, i):
    depth = 1
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            j = s.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == '"':
            i += 1
            while i < n and s[i] != '"':
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
    return n


def close_tick(s, i):
    n = len(s)
    while i < n and s[i] != "`":
        i += 2 if s[i] == "\\" else 1
    return min(i, n)


def scan(s):
    segs, subs = [], []
    cur = Seg()
    word, in_word = [], False
    pending = []
    i, n = 0, len(s)

    def end_word():
        nonlocal word, in_word
        if in_word:
            cur.words.append("".join(word))
        word, in_word = [], False

    def end_seg():
        nonlocal cur
        end_word()
        if cur.words or cur.docs:
            segs.append(cur)
        cur = Seg()

    while i < n:
        c = s[i]
        if c in " \t":
            end_word()
            i += 1
        elif c == "\n":
            owner = cur
            end_seg()
            i += 1
            for seg_ref, tag, strip in pending:
                body = []
                while i < n:
                    j = s.find("\n", i)
                    line = s[i:] if j < 0 else s[i:j]
                    i = n if j < 0 else j + 1
                    check = line.lstrip("\t") if strip else line
                    if check == tag:
                        break
                    body.append(line)
                seg_ref.docs.append("\n".join(body))
            pending = []
            if owner.docs and owner not in segs:
                segs.append(owner)
        elif c == "#" and not in_word:
            while i < n and s[i] != "\n":
                i += 1
        elif c == "\\":
            if i + 1 < n and s[i + 1] == "\n":
                i += 2
            else:
                if i + 1 < n:
                    word.append(s[i + 1])
                in_word = True
                i += 2
        elif c == "'":
            j = s.find("'", i + 1)
            j = n if j < 0 else j
            word.append(s[i + 1:j])
            in_word = True
            i = j + 1
        elif c == '"':
            in_word = True
            i += 1
            while i < n and s[i] != '"':
                if s[i] == "\\" and i + 1 < n:
                    word.append(s[i + 1])
                    i += 2
                elif s.startswith("$(", i):
                    j = close_paren(s, i + 2)
                    subs.append(s[i + 2:j])
                    word.append("$SUB")
                    i = j + 1
                elif s[i] == "`":
                    j = close_tick(s, i + 1)
                    subs.append(s[i + 1:j])
                    word.append("$SUB")
                    i = j + 1
                else:
                    word.append(s[i])
                    i += 1
            i += 1
        elif s.startswith("$(", i):
            j = close_paren(s, i + 2)
            subs.append(s[i + 2:j])
            word.append("$SUB")
            in_word = True
            i = j + 1
        elif c == "`":
            j = close_tick(s, i + 1)
            subs.append(s[i + 1:j])
            word.append("$SUB")
            in_word = True
            i = j + 1
        elif s.startswith("<<", i) and not s.startswith("<<<", i):
            m = re.match(r"<<(-?)\s*(?:'([^']*)'|\"([^\"]*)\"|([^\s;&|()<>]+))", s[i:])
            if m:
                tag = m.group(2) or m.group(3) or m.group(4) or ""
                pending.append((cur, tag, m.group(1) == "-"))
                i += m.end()
            else:
                word.append(c)
                in_word = True
                i += 1
        elif c in ";|()":
            end_seg()
            i += 1
        elif c == "&":
            prev = s[i - 1] if i else ""
            nxt = s[i + 1] if i + 1 < n else ""
            if prev in "<>" or nxt == ">":
                word.append(c)
                in_word = True
            else:
                end_seg()
            i += 1
        else:
            word.append(c)
            in_word = True
            i += 1
    end_seg()
    return segs, subs


def skip_opts(words, with_arg, long_with_arg=()):
    i = 0
    while i < len(words):
        w = words[i]
        if w == "--":
            return words[i + 1:]
        if not w.startswith("-") or w == "-":
            break
        i += 2 if (w in with_arg or w in long_with_arg) else 1
    return words[i:]


def strip_wrapper(prog, rest):
    if prog == "sudo":
        return skip_opts(rest, SUDO_ARG)
    if prog == "timeout":
        rest = skip_opts(rest, TIMEOUT_ARG)
        return rest[1:] if rest else rest
    if prog == "nice":
        return skip_opts(rest, {"-n", "--adjustment"})
    if prog == "env":
        rest = skip_opts(rest, ENV_ARG)
        while rest and ASSIGN.match(rest[0]):
            rest = rest[1:]
        return rest
    if prog in {"command", "nohup", "exec", "setsid", "builtin"}:
        return skip_opts(rest, {"-a"} if prog == "exec" else set())
    if prog == "stdbuf":
        return skip_opts(rest, {"-i", "-o", "-e"})
    if prog == "xargs":
        return skip_opts(rest, XARGS_ARG)
    return None


def check_tf(prog, args):
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-chdir":
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            break
    if i >= len(args):
        return None
    sub = args[i]
    rest = [a for a in args[i + 1:] if not a.startswith("-")]
    if sub in BLOCKED:
        return f"{prog} {sub}"
    if sub == "state" and rest and rest[0] in BLOCKED_STATE:
        return f"{prog} state {rest[0]}"
    if sub == "workspace" and rest and rest[0] == "delete":
        return f"{prog} workspace delete"
    return None


def check_words(words, docs, depth):
    while True:
        while words and (words[0] in KEYWORDS or ASSIGN.match(words[0])):
            words = words[1:]
        if not words:
            return None
        prog = os.path.basename(words[0])
        rest = words[1:]
        if prog in TF_NAMES:
            return check_tf(prog, rest)
        if prog == "command" and rest and rest[0] in {"-v", "-V"}:
            return None
        stripped = strip_wrapper(prog, rest)
        if stripped is not None:
            words = stripped
            continue
        if prog in SHELLS:
            return check_shell(rest, docs, depth)
        if prog == "eval":
            return analyze(" ".join(rest), depth + 1)
        if prog == "find":
            for k, w in enumerate(rest):
                if w in FIND_EXEC:
                    tail = []
                    for t in rest[k + 1:]:
                        if t in {";", "+"}:
                            break
                        tail.append(t)
                    return check_words(tail, [], depth + 1)
        return None


def check_shell(args, docs, depth):
    has_c = False
    i = 0
    while i < len(args):
        a = args[i]
        if a in {"-o", "+o", "-O", "+O"}:
            i += 2
            continue
        if a == "--":
            i += 1
            break
        if a.startswith(("-", "+")) and len(a) > 1:
            if a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
                has_c = True
            i += 1
            continue
        break
    if has_c:
        return analyze(args[i], depth + 1) if i < len(args) else None
    if i < len(args):
        return None
    for body in docs:
        hit = analyze(body, depth + 1)
        if hit:
            return hit
    return None


def analyze(cmd, depth=0):
    if depth > MAX_DEPTH or not cmd:
        return None
    segs, subs = scan(cmd)
    for seg in segs:
        hit = check_words(seg.words, seg.docs, depth)
        if hit:
            return hit
    for sub in subs:
        hit = analyze(sub, depth + 1)
        if hit:
            return hit
    return None


hit = analyze(sys.argv[1])
if hit:
    sys.stderr.write(
        f"guard-tf: blocked `{hit}`. It changes real infrastructure or state. "
        "Ask the user to run it themselves, or to approve it explicitly, "
        "and review the plan output first.\n"
    )
    sys.exit(2)
PY
