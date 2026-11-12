---
name: reproduce-regression
description: Builds copies of the pinned S0 and S1 exports inside its own attempt directory, deploys both locally, and runs one portable PoC with identical input against each through a real interface, keeping setup, PoC, workload, separate logs and the observed behaviour (correct, failure, unknown) in a sealed reproduce.json. Use as the reproduce stage of regression-hunt:regression-hunt, or when handed a campaign, attempt, candidate and handle file. Not for re-running someone else's PoC independently — use regression-hunt:replay-regression.
argument-hint: "<campaign dir> <attempt> <handle file> <candidate>"
allowed-tools: Read Grep Glob Write Bash(shasum -a 256:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/runtime.py wait:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/evidence.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/registry.py check:*)
---

Assignment: $ARGUMENTS

# Reproduce one candidate on S0 and S1

Scripts: `${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/` (`<scripts>`). Record fields:
`${CLAUDE_SKILL_DIR}/../regression-hunt/references/records.md`.

The answer comes from running both builds, not from reading code. Record what happened, not what
you expected. Write only inside `<C>/attempts/<aNNN>/`. Without a campaign, attempt, candidate and
handle file, stop and point to `regression-hunt:regression-hunt`.

Write every script call with the literal absolute path (`<scripts>` expanded) and literal absolute
campaign paths; never put the scripts, the campaign or the attempt in shell variables. The
transcript is part of the evidence. Directories are created by the Write tool, or by a plain
`mkdir` that prompts.

## Gate

You will run the project's build and code. The brief must quote the user's approval and that
approval must explicitly allow running the project's commands. Show your plan first in your
output: the build command, the PoC, the input, the two deployments and the directories. If the
approval is missing or does not cover running code, stop after the plan and return `blocked`
("needs approval to run project commands"). Builds, copies and PoC runs are not pre-allowed;
they prompt.

The `Approval:` line holds the user's words only; never widen or paraphrase it. A denial from
the harness, a permission prompt or a safety classifier is a blocker: return `blocked` with it
and never route around it.

## 1. Handle and inputs

1. `python3 <scripts>/runtime.py wait <C>/runtime/<aNNN>-handle` → your handle (exit 1 → blocked).
2. `python3 <scripts>/evidence.py verify <C> <rel>` for the prepare, hunt and candidate records.
3. Read the candidate file, `source.json`, the boundary notes, security docs and guidance.

## 2. Deploy S0 and S1

1. Copy the exports: `cp -R <C>/<prepare dir>/snapshot/S0 <C>/attempts/<aNNN>/build/S0`, same for
   S1. Never build in the snapshot, the target checkout or another attempt's directory.
2. Build each copy with the project's documented command and the environment from the brief (Go:
   `GOCACHE=<C>/attempts/<aNNN>/gocache GOFLAGS=-buildvcs=false GOTOOLCHAIN=local`). Keep build
   output in `logs/build-S0.log` and `logs/build-S1.log`. A missing toolchain is `blocked`: never
   install anything.
3. Start services the path needs (local processes or local containers only). No cloud, cluster,
   Terraform backend or remote host: a candidate that needs one is `blocked` with the gap.

## 3. One PoC, both sides

1. Trace the candidate to a real entry point: the binary's CLI, an HTTP request, a public API.
   A unit test, a mock, an extracted function or an invented internal state is not proof.
2. Write `attempts/<aNNN>/poc/`: the PoC (one script taking the deployment as its argument),
   `workload` (input and sanitised config, no revision-specific addresses), `setup.md` (steps to
   repeat the deployment). Everything it needs lives there; nothing is fetched at run time.
3. Run it against S0, then S1, with the same input and comparable config. Capture the command,
   stdout, stderr and exit code of each into `logs/S0.log` and `logs/S1.log`.
4. Judge each side from its log: `correct` (the promised behaviour, a refusal included), `failure`
   (the defect), `unknown`. Only claim what ran.

## 4. Record and seal

`attempts/<aNNN>/reproduce.json`: common fields, `candidate`, `source` (the prepare stage's
`source.json`), `setup`, `poc`, `workload`, `runs` (S0 then S1: `state`, `revision` = source s0/s1,
`deployment`, `command`, `log`, `behavior`), `build_dirs` (`["attempts/<aNNN>/build"]`),
`artifacts` (`poc`, `logs`, `build`). Write the versions of the tools used and where temporary
resources went (stopped, removed, left) into `logs/environment.txt`; release resources but never
delete evidence. Blocked: keep `runs` empty and say exactly what is missing.

```bash
python3 <scripts>/evidence.py seal <C> attempts/<aNNN>/reproduce.json
python3 <scripts>/registry.py check <C> <aNNN> attempts/<aNNN>/reproduce.json
```

Return the four lines from the brief.

## Limits

- No install, no cloud, no remote hosts, no `kubectl`/`helm`/`terraform apply`/`ansible-playbook`.
- The target checkout is never touched; no `git worktree`. Never write `runtime/`, `scope.json`,
  `registry.json` or `campaign.json`. No secrets in logs or configs.
