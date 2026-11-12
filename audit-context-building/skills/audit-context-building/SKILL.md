---
name: audit-context-building
description: Maps code nobody on the team has read before an audit starts — ranks the units correctness hangs on, gives each one to a function-analyzer agent that records its invariants, its unenforced assumptions and what every callee does on every path, then merges the records into a dossier under $TMPDIR. Covers Go, Python, Bash, TypeScript, Ansible, Terraform and GitLab CI. Use when preparing an audit, threat model or architecture review of an unfamiliar repo, or when asked what one handler relies on and assumes. Not for hunting bugs or insecure values — use insecure-defaults:audit.
argument-hint: "[path or module] [units=N] [function name]"
allowed-tools: Read Grep Glob Write Agent Bash(git ls-files:*) Bash(git rev-parse:*) Bash(git log:*) Bash(printenv TMPDIR)
---

Request: $ARGUMENTS

# Audit context building

Bug hunting on code you do not understand produces noise: plausible findings that the
surrounding code already rules out, and real ones missed because a callee was assumed to do
what its name says. This skill comes first. It produces understanding, written down so that
the hunting phase can start from it, and it produces no findings.

**Dispatched as `audit-context-building:function-analyzer`?** Your agent file is the whole
brief. Follow it and ignore everything below; never dispatch further agents.

## Right skill?

Use it on code the requester does not know. On code they already know well, it repeats what
they could tell you; say so and offer the hunting skills instead.

| What the user actually asks for | Where it belongs |
|---|---|
| bugs, unsafe defaults, hardcoded or fallback secrets | `insecure-defaults:audit` |
| a pattern or ruleset scan | `static-analysis:semgrep` |
| other places with the same flaw as one they point at | `variant-analysis:variant-analysis` |
| an API, role or module interface that is easy to misuse | `sharp-edges:sharp-edges` |
| a security review of an MR, PR or commit range | `differential-review:differential-review` |
| Go idiom or correctness | `golang:review` |

A request that quotes one concrete skipped check and asks where else it happens is the
variant case, even when it says "understand". Do not start here.

## Rules for every stage

- **No verdicts.** No vulnerability names as conclusions, no severity or CVSS, no fixes, no
  proofs of concept. Something the code relies on that nothing enforces is written down as an
  *unenforced assumption*; judging it belongs to the hunting phase.
- **Cite or ask.** A structural claim carries a line (`path:L42` or `L40-L47`). What cannot be
  cited becomes an open question. Names prove nothing: `validateX` validates whatever its body
  says. Hedging words (*probably*, *should*, *seems*) are not allowed; each one turns into a
  cited claim or a question.
- **Read only.** No Edit, no execution of the code (no build, test, script, playbook,
  `terraform`, request), no network, no installs. Shell access is limited to `git ls-files`,
  `git rev-parse`, `git log` and `printenv TMPDIR`.
- **Writes only in the notes directory**, with Write and absolute paths. Nothing in the repo.
- **Secrets** are cited by location; a value is written `<redacted>`.
- **No approval gates.** Nothing is downloaded, run or changed, so the stages run straight
  through.

## Stage 1. Orient

**Notes directory.** `printenv TMPDIR` gives the temp root; if it prints nothing, use `/tmp`.
Strip trailing slashes from it (macOS `$TMPDIR` ends in `/`).

- Git repository: root from `git rev-parse --show-toplevel`, `<repo>` is its last path
  segment, `<sha>` is `git rev-parse --short HEAD`. Directory:
  `<tmp>/audit-context-<repo>-<sha>/`.
- Not a git repository (`git rev-parse` fails): the root is the current directory, and the
  directory is `<tmp>/audit-context-<dirname>-nogit/`. List files with Glob instead of
  `git ls-files`.
- If that directory already holds a `DOSSIER.md`, add `-2`, `-3`, … rather than overwrite.

Inside it: `functions/NN-<name>.md`, one per unit (`NN` = 01, 02, … in analysis order;
`<name>` lowercase, characters outside `a-z0-9.-` replaced with `-`), and `DOSSIER.md`.

**Survey, broad and shallow.** `git ls-files`, then the manifests and entry points: `go.mod`,
`pyproject.toml`, `package.json`, `main` packages and route tables, role `meta/` and
`argument_specs`, `variables.tf`, CI `spec: inputs:`, `.gitlab-ci.yml`. A focus path or module
from the user narrows this to that area plus whatever it calls. Answer four questions, each
with lines:

1. **Parts:** packages, modules, roles, components.
2. **Ways in:** what an outside party can trigger, and who can reach each one.
3. **Actors:** who calls in, and how much each is trusted.
4. **Lasting state:** what survives a single call (rows, files, caches, maps, Terraform state,
   CI artifacts).

What these mean in each stack (Go and Python services, TypeScript, CLIs and Bash, Ansible,
Terraform, GitLab CI) is in [stacks.md](references/stacks.md). Read the section for every
stack present.

**Rank units** by how much correctness rests on them:

- validators and parsers of anything an outside actor controls;
- enforcers of a bound, quota, permission or tenancy split;
- writers of the lasting state;
- whatever sits between an untrusted actor and that state.

Getters, pure formatting and pass-through wrappers do not make the list. Keep the 12 top units;
a number from the user replaces 12. When the user names one function, that unit alone is
analysed, and the rest of the ranking is still listed as not analysed. Units past the cut go
to the not-analysed list with one line on why each ranked where it did.

## Stage 2. Analyze, one agent per unit

Dispatch `audit-context-building:function-analyzer` (that exact name as `subagent_type`) once
per kept unit. **This is not optional**: not for one unit, not for a file small enough to read
in a minute. The record each agent returns is what Stage 3 and every later phase consume, and
reading the code yourself produces no record. At most 5 agents run at once: send up to five
Agent calls in one message, wait, then the next batch.

Each brief contains:

```text
repoRoot: <absolute repo root>
tmpRoot: <resolved temp root, no trailing slash; required>
unit: <name> in <path> (L<start>-L<end>)
why: <the ranking reason>
orientation: <3-6 lines: actors, ways in, lasting state relevant to this unit>
output: <notes dir>/functions/NN-<name>.md
```

**When a dispatch fails** (the Agent tool is unavailable or refused, the agent errors, times
out or returns nothing): stop the stage. Tell the user which dispatch failed and the error as
reported, list the units already done with their notes paths, and end there. Do not analyse
the remaining units inline as a substitute.

**Check each record** against the format in [records.md](references/records.md#returned-record):
all nine keys present, every invariant with `evidence:`, every assumption with
`establishedBy:` or ending in `nothing found`, `analysisFile` equal to the path you gave. A
record that fails goes back once to a fresh agent for the same unit with the gap named. A
second failure is listed in the dossier and in the reply as an unreliable record, unused. A
reply of `refused:` means the output path was wrong: correct it and redispatch once.

## Stage 3. Synthesize the dossier

Write `DOSSIER.md` from the returned records. Open a prose file only when a record line is
too terse to place. The section order is fixed and given in
[records.md](references/records.md#dossier). What each section is for:

- **State:** each piece of lasting state with every unit that reads it and every unit that
  writes it, and the invariant those writers jointly have to keep.
- **Flows:** ways in traced end to end through the analysed units.
- **Reach:** actor → way in → what it can touch.
- **Hotspots:** where branching, coupling or shared state piles up.
- **Joined invariants:** facts that hold only because two units cooperate, which neither
  record states alone. Cite both records.
- **Disagreements:** two records that contradict each other. Quote both; do not pick a side.
- **Unenforced assumptions:** every `nothing found` line, copied verbatim, with its unit and
  line.
- **Open questions:** all of them, deduplicated, each naming the unit that raised it.
- **Not analysed:** ranked units past the cut, unreliable records, failed dispatches.

## Stage 4. Hand over

Write the dossier before replying. The reply carries, in this order:

1. `Notes:` the absolute notes directory (resolved, never the literal `$TMPDIR`);
2. the analysed units, one line each: `NN name — path:Lstart-Lend`;
3. every unenforced assumption with its `path:line`;
4. the open questions;
5. `Not analysed:` the list, or `nothing` when every ranked unit was analysed;
6. a suggested next phase from: `insecure-defaults:audit`, `static-analysis:semgrep`,
   `sharp-edges:sharp-edges`, `differential-review:differential-review`, naming which
   assumptions or hotspots it should start from.

```text
Notes: /var/folders/k2/x7/T/audit-context-ledgerd-91be0c4/
01 PostTransfer — internal/api/transfer.go:L18-L71
02 debit — internal/book/debit.go:L9-L40
Unenforced: amount > 0 on the refund path (internal/book/debit.go:L22) — nothing found
Open: unclear; need to inspect the gateway config that sets X-Branch
Not analysed: 03 statementPDF (formatting only past the cut)
Next: insecure-defaults:audit on internal/book, starting from debit.go:L22
```

If the dossier cannot be written, say why and put its content in the reply instead.

## Limits

- Static reading only. A question only running the code could answer becomes an open
  question naming what would have to run.
- Settings outside the repository (CI project variables, protected branches, gateway or
  proxy config, cloud IAM) are recorded as established outside the repo, or `nothing found`,
  never assumed.
- `git log` is allowed for history only; never pass `--output`, which writes a file.
- No edits, no network, no installs, no commits, no comments anywhere.
