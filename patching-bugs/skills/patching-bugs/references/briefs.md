# Agent briefs

Each stage runs in a fresh `general-purpose` agent dispatched with the Agent tool. The brief is
all it knows. Never paste another agent's transcript or summary into a brief; give paths.

## Identity strings

Give each agent a distinct identity and tell it to write that exact string into its record's
`agent` field: `reproducer@<run-name>`, `validator@<run-name>`, `patcher-<N>@<run-name>`,
`prover-<N>@<run-name>`. `verdict.py` blocks a run where reproducer and validator, or the patcher
and prover of one attempt, share a string.

## Parts of every brief

1. First line: `Load the skill patching-bugs:<stage> with the Skill tool and follow it.`
2. Checkout (absolute), run directory (absolute), baseline commit (40 hex), identity string.
3. Approval: the user's approving words, quoted verbatim, and the commands they cover (build, PoC,
   tests, and for the patcher the local `git commit -s`). If the user has not approved, do not
   dispatch.
4. Toolchain environment to prefix: for Go `GOCACHE=<TMPDIR>/gocache GOFLAGS=-buildvcs=false`,
   plus `PATH=<TMPDIR>/bin:$PATH` when the git wrapper from recipes.md is in use.
5. Guidance: the block printed by `records.py guidance`, verbatim, labelled by file name and
   commit. If it cannot fit, do not dispatch; report the blocker.
6. Paths: literal absolute paths in every command, no shell variables for the run directory,
   scripts or checkout.
7. Return format: the record path(s), one status word, and failures with receipt paths. No prose
   retelling.

## Stage-specific parts

| Stage | Also give | Never give |
|---|---|---|
| reproduce | `finding.json` path, the chosen recipe and build argv | any plan for the fix |
| validate | `finding.json` and the `reproduce/` directory path | the reproducer's transcript, summary or opinion |
| implement | `finding.json` path, attempt number N, the earlier attempts' proof failures and gaps (copied from `prove/attempt-*/prove.json` and `verdict.py` output) | the prover's identity |
| prove | baseline, `patch_commit`, `repair_scope`, the `reproduce/` package, attempt N | the patcher's reasoning or its claim that it works |

## After the agent returns

Do not trust the summary. Run `records.py check <run>`, open the record, and look at one raw
receipt yourself before moving on.
