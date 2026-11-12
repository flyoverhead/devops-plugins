---
name: adjudicate-regression
description: Decides one candidate from sealed evidence — source, setup, PoC, raw S0/S1 logs and the project's security promises — as REPRODUCED_REGRESSION, INCOMPLETE_FIX, LATENT_BUG, PREEXISTING_BUG, REJECTED or UNRESOLVED, with category, severity, likelihood and nine cited checks for a confirmation, in a sealed decision.json. Use as the adjudication stage of regression-hunt:regression-hunt, or when handed a campaign, attempt, candidate and handle file. Not for producing missing evidence — use regression-hunt:reproduce-regression.
argument-hint: "<campaign dir> <attempt> <handle file> <candidate>"
allowed-tools: Read Grep Glob Write Bash(git log:*) Bash(git show:*) Bash(gh pr list:*) Bash(gh pr view:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/runtime.py wait:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/evidence.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/registry.py check:*)
---

Assignment: $ARGUMENTS

# Adjudicate one candidate

Scripts: `${CLAUDE_SKILL_DIR}/../regression-hunt/scripts/` (`<scripts>`). Record fields:
`${CLAUDE_SKILL_DIR}/../regression-hunt/references/records.md`.

You did not run the experiments and you do not repair them. Read the raw material, not summaries.
Write only inside `<C>/attempts/<aNNN>/`. Without a campaign, attempt, candidate and handle file,
stop and point to `regression-hunt:regression-hunt`.

Write every script call with the literal absolute path (`<scripts>` expanded) and literal absolute
campaign paths; never put the scripts, the campaign or the attempt in shell variables. The
transcript is part of the evidence. Directories are created by the Write tool, or by a plain
`mkdir` that prompts.

## 1. Handle and inputs

1. `python3 <scripts>/runtime.py wait <C>/runtime/<aNNN>-handle` → your handle (exit 1 → blocked).
2. `python3 <scripts>/evidence.py verify <C> <rel>` for every sealed input.
3. Read: the candidate file; S0 and S1 source at the changed lines; each experiment's `setup`,
   `poc`, `workload` and both logs; the security docs and guidance.

## 2. Decide

Work through these in order; the first that holds decides.

| Outcome | When (cite evidence for each) |
|---|---|
| `REJECTED` | the change is intentional (commit message, docs, tests say so), the expectation is unsupported, or the path is unreachable for any real user or attacker |
| `PREEXISTING_BUG` | S0 already fails the same way |
| `LATENT_BUG` | the defect existed in S0 and the change only exposes it (S0 passes and S1 fails is not enough to rule this out) |
| `INCOMPLETE_FIX` | the change meant to repair something and missed an input source, caller or usage |
| `REPRODUCED_REGRESSION` | every condition below holds |
| `UNRESOLVED` | anything else; missing proof is never `REJECTED` |

A confirmation needs all of: the behaviour is supported (docs, tests, README), the failure is
reachable through a real interface, S0 is `correct` and S1 is `failure` with the same PoC and
input in both the reproduction and the replay, the change caused it, the exclusions above are
ruled out with cited evidence, and reproduction, replay and you are three different agents.
Synthetic unit tests, mocks, extracted functions, simulated dependencies, invented states or
privileges granted only for the test do not count.

Security candidates: say what the attacker must control or already hold, and cite whether the
project promises protection against that attacker (threat model, security docs; else derive it from
the code and supported deployment, never assume extra access). A scenario the project excludes is
not a security regression and is not relabelled functional unless a broken supported workflow is
shown separately.

Before calling a finding new, check known issues and PRs (`gh pr list --search <term> --state all`
when the remote is GitHub and `gh` works, `git log --grep` otherwise); if neither is possible,
write "novelty unknown".

Ratings for a confirmation, each with a reason; they do not prove validity:

- severity: Low (narrow or easy to recover), Medium (material feature loss, repeatable disruption,
  limited data exposure), High (broad disruption, substantial sensitive-data compromise, serious
  integrity loss), Critical (exceptional, widespread compromise with explicit evidence);
- likelihood: Low (unusual configuration or demanding prerequisites), Medium (plausible
  non-default workflow), High (routine operation).

UNRESOLVED `reason`: one paragraph separating what was observed from what is missing; pair each
plausible cause with a check or a maintainer question.

Duplicate requests: establish the shared root cause first; then `duplicate_of` the canonical id
with the same outcome. Keep every change mapping.

## 3. Record and seal

`attempts/<aNNN>/decision.json`: common fields, `candidate`, `outcome`, `reason` (with file:line
and log citations), `evidence` (paths from your inputs or their sealed packages, e.g. the
experiment logs). For `REPRODUCED_REGRESSION` add `reproduction`, `replay`, `category`,
`severity`, `likelihood`, `severity_reason`, `likelihood_reason` and the nine `checks`
(`supported_behavior`, `reachability`, `introduced_defect` SUPPORTED; `incomplete_fix`,
`latent_bug`, `preexisting_bug`, `intentional_change`, `unsupported_expectation` REFUTED;
`security_scope` SUPPORTED for VULNERABILITY, otherwise NOT_APPLICABLE), each with `conclusion`,
`reason` and `evidence`. If a needed input is missing, return it to the caller as a gap rather than
guessing; `status` `blocked` with `outcome` `UNRESOLVED`.

```bash
python3 <scripts>/evidence.py seal <C> attempts/<aNNN>/decision.json
python3 <scripts>/registry.py check <C> <aNNN> attempts/<aNNN>/decision.json
```

Return the four lines from the brief.

## Limits

- Forbidden flags: `--output`, `--ext-diff` and `--textconv` on `git log` and `git show`; `--web`
  on `gh pr list` and `gh pr view`.
- Run nothing from the project. GitHub is read-only. Never write `runtime/`, `scope.json`,
  `registry.json` or `campaign.json`.
