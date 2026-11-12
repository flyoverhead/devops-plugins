# sharp-edges

Reviews interfaces for how easily they are used wrongly: the default nobody changes, the README
example everyone copies, the shortest call that compiles. Each finding comes with the smallest
misuse that shows it, the traced outcome and a fix to the design itself. Read-only: it greps and
reads, never edits and never runs the target.

```text
/plugin install sharp-edges@devops
```

## What it reviews

| Interface | Where the choice points are |
|---|---|
| Go, Python, TypeScript packages | exported functions, constructors, config structs |
| CLIs and services | flags, environment variables, config files |
| Bash scripts | arguments and the variables they read |
| Ansible roles | `defaults/`, `meta/argument_specs.yml`, variables used in tasks and templates |
| Terraform modules | `variable` blocks and the resources each reaches |
| GitHub Actions | triggers, `uses:` refs, `permissions:`, workflow and action `inputs`, secrets |
| GitLab CI | `include:` and its `inputs`, `rules:`, variables, images |

Findings are tagged with one of six categories: algorithm and mode selection, dangerous
defaults, primitive instead of semantic types, configuration cliffs, silent failures and
stringly-typed security.

## Usage

```text
/sharp-edges:sharp-edges                        # current directory
/sharp-edges:sharp-edges roles/edge_proxy       # one role
/sharp-edges:sharp-edges . pkg/auth .github     # named interfaces
```

Or in plain words: "other teams will consume this module, how easy is it to misuse?",
"look for footguns in this API", "is this role secure by default?".

## How it works

1. **Map** the interfaces in scope and every choice a caller makes through them.
2. **Probe** each choice with `0`, `""`, null, `[]`, `-1`, a wrong boolean, a right-type
   wrong-meaning value and an invalid value, by reading the code.
3. **Picture** three callers: an adversary who controls input, a developer who copies the first
   example, and one who misreads the contract.
4. **Prove** each candidate with a minimal misuse and a traced outcome, or drop it.
5. **Report** by severity (CRITICAL to LOW), then list what was and was not reviewed.

For a large scope it hands one interface each to the `sharp-edges-analyzer` agent, five at a
time. The agent has Read, Grep and Glob only.

The reference catalogue covers crypto APIs, authentication and sessions, config schemas, Go,
Python, JavaScript/TypeScript, Bash, lessons from native libraries, Ansible and YAML,
Terraform, GitHub Actions (first CI section) and GitLab CI (second).

## Not this plugin

- If the risky value is already written into the code (a fallback secret, a switch set to
  off), run `insecure-defaults:audit`.
- If you are looking at a change set, a branch or a range of commits, run
  `differential-review:differential-review`.
- If the question is Go idiom or whether the code is correct, run `golang:review`.
- If a role should match the layout and lint conventions, run `ansible:role-checker`.
- If you are after credentials buried in old commits, nothing here helps.

## Required tools

None beyond `grep` and `git`. Nothing is installed, and `gh` is not used.

## Tests

```bash
python3 -m pytest sharp-edges/tests -q
```

The tests check that the skill links every reference and every link resolves, that each
catalogue entry carries its Bites/Spot/Fix lines, that the GitHub Actions reference leads with
its five patterns and comes before GitLab CI, that code blocks parse, and that the skill and the
agent stay read-only.
