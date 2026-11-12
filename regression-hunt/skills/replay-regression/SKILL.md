---
name: replay-regression
description: Replays a sealed reproduction independently — verifies the package, rebuilds S0 and S1 from the pinned exports in its own attempt directory, runs the byte-identical PoC and workload with only the attacker or user access the candidate claims, and records any divergence in a sealed replay.json. Use as the replay stage of regression-hunt:regression-hunt, or when handed a campaign, attempt, candidate, reproduction record and handle file. Not for first reproduction of a candidate — use regression-hunt:reproduce-regression.
argument-hint: "<campaign dir> <attempt> <handle file> <candidate> <reproduce.json>"
allowed-tools: Read Grep Glob Write Bash(shasum -a 256:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/runtime.py wait:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/evidence.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/registry.py check:*)
---

Assignment: $ARGUMENTS

# Replay a reproduction

Scripts: `${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/` (`<scripts>`). Record fields:
`${CLAUDE_SKILL_DIR}/../regression-hunt/references/records.md`.

You are the second, independent run. Use the reproduction's PoC and workload as they are and build
everything else yourself. Write only inside `<C>/attempts/<aNNN>/`. Without a campaign, attempt,
candidate, reproduction record and handle file, stop and point to `regression-hunt:regression-hunt`.

Write every script call with the literal absolute path (`<scripts>` expanded) and literal absolute
campaign paths; never put the scripts, the campaign or the attempt in shell variables. The
transcript is part of the evidence. Directories are created by the Write tool, or by a plain
`mkdir` that prompts.

## Gate

As for reproduction: the brief must quote an approval that must explicitly allow running the
project's commands. Show the plan first (rebuild commands, the PoC, both deployments). Missing
approval → return `blocked` after the plan.

The `Approval:` line holds the user's words only; never widen or paraphrase it. A denial from
the harness, a permission prompt or a safety classifier is a blocker: return `blocked` with it
and never route around it.

## 1. Handle and inputs

1. `python3 <scripts>/runtime.py wait <C>/runtime/<aNNN>-handle` → your handle (exit 1 → blocked).
2. `python3 <scripts>/evidence.py verify <C> <rel>` for prepare, hunt, candidate and the
   reproduction record. A failed verification → `blocked`.
3. Read the reproduction's `setup`, `poc`, `workload` and logs. Ignore its conclusions.

## 2. Rebuild

1. Copy the PoC and workload files into `attempts/<aNNN>/poc/` with `cp -p`, then compare them
   with `shasum -a 256` against the reproduction's: they must be identical. Never edit them. A PoC
   that needs a change means a new reproduction and a new replay: return `blocked` and say why.
2. `cp -R` the S0 and S1 exports from the prepare snapshot into `attempts/<aNNN>/build/`; never
   reuse another attempt's build output. Build with the project's command and the brief's
   environment; logs in `logs/build-S0.log`, `logs/build-S1.log`. Never install anything.

## 3. Run

1. Check reachability: run with only the access the candidate claims (no extra flags, keys or
   privileges granted for convenience). If the trigger needs more, record that.
2. Run the unchanged PoC against S0, then S1. Logs go to `logs/S0.log` and `logs/S1.log` in your own
   directory.
3. Judge each side from your own logs. If you see something other than the reproduction did, write
   the divergence in `summary`.

## 4. Record and seal

`attempts/<aNNN>/replay.json`: the same fields as `reproduce.json` (common fields, `candidate`,
`source`, `setup`, `poc`, `workload`, `runs`, `build_dirs`) with your own paths. `inputs` include
the reproduction record. `artifacts`: `poc`, `logs`, `build`.

```bash
python3 <scripts>/evidence.py seal <C> attempts/<aNNN>/replay.json
python3 <scripts>/registry.py check <C> <aNNN> attempts/<aNNN>/replay.json
```

Return the four lines from the brief.

## Limits

- Never repair or extend the PoC or workload. No install, no cloud, no remote hosts.
- The target checkout is never touched; no `git worktree`. Never write `runtime/`, `scope.json`,
  `registry.json` or `campaign.json`. No secrets in logs.
