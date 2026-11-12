# fp-check

Settles whether security findings are real. Each finding that points at a `path:line` is
restated, traced from source to sink, tested for attacker control and impact, and run through
six gates. The answer per finding is `TRUE POSITIVE` or `FALSE POSITIVE` with the deciding
evidence. The repository is only read; PoCs go to `$TMPDIR` and run only after you say yes.

```text
/plugin install fp-check@devops
```

## Input

| Source | Example |
|---|---|
| Scanner output | SARIF, gosec / semgrep / bandit lists, a findings file with `path:line` |
| Review findings | from `insecure-defaults:audit`, `differential-review:differential-review`, `sharp-edges:sharp-edges`, or a person |
| GitHub code scanning | the alert JSON pasted into the chat (`rule.id`, `most_recent_instance.location`, message) |

Alerts are never fetched: `gh` is not used. Give only an alert URL or number and the skill asks
for the JSON. Code, secret, IaC and CI findings all work as long as they have a location.

## Usage

```text
/fp-check:fp-check findings.md
/fp-check:fp-check internal/api/export.go:58
```

Or in plain words: "is this a false positive?", "which of these scanner hits are exploitable?",
"can we close this code-scanning alert?".

## How it works

1. **Step 0** restates each claim: root cause, trigger, impact, threat model, class, callers,
   history. Incoherent claims usually fall apart here.
2. **Route.** Simple, single-component findings take the standard path; vague claims,
   multi-module paths, races and logic bugs take the deep path. Two checkpoints on the
   standard path can escalate.
3. **Standard path:** data flow, exploitability, impact, pseudocode PoC, a seven-question
   devil's advocate, gate review.
4. **Deep path:** a tracked task graph. `data-flow-analyzer` (Phase 1),
   `exploitability-verifier` (Phase 2) and `poc-builder` (Phase 4) do the delegated phases;
   impact, a thirteen-question devil's advocate and the gate review stay with the skill.
5. **Gates:** process, reachability, real impact, PoC validation, math bounds, environment.
   All six pass, or the verdict is FALSE POSITIVE naming the failed gate.
6. **Batch extras:** an exploit-chain pass over rejected findings, then a summary with counts
   and both lists.

A skill-scoped SubagentStop hook checks that each phase agent returned every section of its
report. Its matcher limits it to those three agents, so it costs one small model call per
phase-agent stop and nothing for other subagents. A report handed back through the
`SubagentHandback` tool passes unchecked, and a second miss is let through, not looped.

## Safety

- No edits, no checkouts; older code via `git show`, never with `--output`, `--ext-diff` or
  `--textconv`.
- PoCs only under `$TMPDIR/fp-check-<repo>/bug-<N>/`, with concrete values.
- Running a PoC needs an explicit yes naming the exact command; unit-test PoCs run only in a
  throwaway clone. Nothing is ever aimed at a real host, service, cloud API, secret store or
  code host.
- Nothing is posted or dismissed anywhere; a dismissal reason is suggested in words.
- Secret values are shown as `<redacted>`.

## Not this plugin

- A CVE, advisory, Dependabot alert, `govulncheck` or Trivy result on a dependency or image:
  `vulnerability-triage-brocards:vulnerability-triage-brocards`.
- Looking for new bugs: `insecure-defaults:audit` or `static-analysis:semgrep`; for a PR or
  commit range, `differential-review:differential-review`.
- Fixing a confirmed finding: no skill in this marketplace does security fixes.
- Go correctness: `golang:review`. Ansible role conformance: `ansible:role-checker`.

## Required tools

None beyond `grep` and `git`. Nothing is installed. Running a PoC needs the project's own
toolchain, and only after your yes.

## Tests

```bash
python3 -m pytest fp-check/tests -q
```
