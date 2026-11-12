---
name: report-regressions
description: Reconciles a regression campaign's index with its frozen scope, assigned changes and accepted candidates, renders index.html, report.md and report.json with report.py into its own attempt directory, checks the counts and links, and seals report-stage.json — blocked on any integrity failure, never repairing decisions or hashes. Use as the report stage of regression-hunt:regression-hunt, or when handed a campaign, report attempt and handle file. Not for deciding a candidate — use regression-hunt:adjudicate-regression.
argument-hint: "<campaign dir> <attempt> <handle file>"
allowed-tools: Read Grep Glob Write Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/runtime.py wait:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/evidence.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/registry.py check:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/registry.py show:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/report.py:*)
---

Assignment: $ARGUMENTS

# Report a campaign

Scripts: `${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/` (`<scripts>`). Record fields:
`${CLAUDE_SKILL_DIR}/../regression-hunt/references/records.md`.

Write only inside `<C>/attempts/<aNNN>/`. Without a campaign, report attempt and handle file, stop
and point to `regression-hunt:regression-hunt`.

Write every script call with the literal absolute path (`<scripts>` expanded) and literal absolute
campaign paths; never put the scripts, the campaign or the attempt in shell variables. The
transcript is part of the evidence. Directories are created by the Write tool, or by a plain
`mkdir` that prompts.

## 1. Handle and inputs

1. `python3 <scripts>/runtime.py wait <C>/runtime/<aNNN>-handle` → your handle (exit 1 → blocked).
2. `python3 <scripts>/registry.py show <C>` and read `campaign.json`. Every change of the frozen
   scope must be indexed; every accepted candidate must appear under its change.
3. `python3 <scripts>/evidence.py verify <C> <rel>` for each record the index points to.

## 2. Render

```bash
python3 <scripts>/report.py <C> --output attempts/<aNNN>/report
```

Exit 1 means an integrity problem (index differs from the scope, a record not accepted, a seal that
no longer verifies); nothing was written. Do not fix records, decisions or hashes: return `blocked`
with the exact message. A decision that fails the confirmation rules is shown as UNRESOLVED with
the reason; that is a result, not an error.

## 3. Inspect

Open `report.md` and `report.json`. Check that the counts match the findings, every change has a
coverage line, every confirmed finding has a verification label, and the evidence links resolve to
files in the campaign. Problems → `blocked` with the list.

## 4. Record and seal

`attempts/<aNNN>/report-stage.json`: common fields with `change` `campaign`, `inputs` as assigned,
`artifacts` `["attempts/<aNNN>/report"]`, `summary` (the counts, or the validation errors),
`security_review` (which records were verified).

```bash
python3 <scripts>/evidence.py seal <C> attempts/<aNNN>/report-stage.json
python3 <scripts>/registry.py check <C> <aNNN> attempts/<aNNN>/report-stage.json
```

Return the four lines from the brief; the record line names `report-stage.json` and the result line
names `attempts/<aNNN>/report/index.html`.

## Limits

- Never edit decisions, seals, `registry.json`, `campaign.json`, `scope.json` or `runtime/`.
- The report holds agent conclusions pending human review; say so wherever you quote it.
