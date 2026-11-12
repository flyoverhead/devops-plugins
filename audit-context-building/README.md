# audit-context-building

The step before an audit: learn what the important parts of an unfamiliar codebase need,
promise and call, and write it down. It ranks the units that correctness depends on, sends one
analyzer agent to each, and merges what they return into a dossier the hunting phase starts
from. It reports no findings: anything the code relies on that nothing enforces is recorded as
an unenforced assumption, with its line.

```text
/plugin install audit-context-building@devops
```

## Usage

```text
/audit-context-building:audit-context-building                     # whole repo, top 12 units
/audit-context-building:audit-context-building internal/billing    # focus on one area
/audit-context-building:audit-context-building units=20            # more units
/audit-context-building:audit-context-building ApplyRefund         # exactly one function
```

Or in plain words: "we start auditing this repo and nobody knows it", "prep for a threat
model", "walk me through this handler: what it does, depends on and assumes".

Stacks: Go and Python services, TypeScript, CLIs and Bash, Ansible roles, Terraform modules
and GitLab CI.

## How it works

1. **Orient.** A broad, shallow read of the file list, manifests and entry points. Every
   answer cites a line:
   - which state outlives a single call;
   - who calls in, and how far each caller is trusted;
   - which entry points those callers can reach;
   - which packages, roles or components make up the code.

   Units are ranked by how much rests on them:
   input validators, bound and permission enforcers, writers of lasting state and anything
   between an untrusted actor and that state. The top 12 are kept.
2. **Analyze.** One `function-analyzer` agent per unit, at most five at a time, even when
   there is only one unit. Each one follows every callee it can read on every path, treats the
   rest as black boxes, writes its notes and returns a short record.
3. **Synthesize.** `DOSSIER.md` is built from the records: who reads and writes each piece of
   state, end-to-end flows, what each actor can reach, hotspots, invariants that only hold
   across units, records that disagree, and every unenforced assumption.
4. **Hand over.** The chat reply gives the notes path, the analysed units, the unenforced
   assumptions with lines, open questions, what was not analysed, and the hunting skill to run
   next.

If an agent dispatch fails, the run stops and says so. It never falls back to reading the
units inline.

## Output

`$TMPDIR/audit-context-<repo>-<short-sha>/` (`/tmp` when `TMPDIR` is unset;
`audit-context-<dir>-nogit/` outside a git repository):

- `functions/NN-<name>.md` holds the analysis of each unit: purpose, inputs and assumptions,
  outputs, a block-by-block walk, dependencies and open questions;
- `DOSSIER.md` holds the synthesis.

## Not for

- If you want bugs, unsafe defaults or leaked secrets → `insecure-defaults:audit`.
- If you want a ruleset scan → `static-analysis:semgrep`.
- If you want more copies of a bug you already found → `variant-analysis:variant-analysis`.
- If you want an interface checked for easy misuse → `sharp-edges:sharp-edges`.
- If you want a diff or PR reviewed → `differential-review:differential-review`.
- If you want Go idiom or correctness checked → `golang:review`.

## Safety

- Read-only: no edits, no execution of the code, no network, no installs.
- Pre-approved shell commands: `git ls-files`, `git rev-parse`, `git log` (never with
  `--output`) and `printenv TMPDIR`.
- Files are written only in the notes directory. Each agent writes only the one path it is
  given. It refuses a brief without a temp root, any path that is not
  `<temp root>/audit-context-<dir>/functions/NN-<name>.md`, and any path inside the
  repository. Paths are compared without trailing slashes and without a leading `/private`.
- Secret values are never quoted, only their locations.

## Tests

```text
python3 -m pytest audit-context-building/tests -q
claude plugin eval ./audit-context-building --trust-plugin --scaffold --no-publish --allow-tools Write Edit Bash
```
