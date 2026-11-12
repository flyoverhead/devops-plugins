---
name: fp-check
description: Decides whether each security finding at a path:line — scanner output, a review finding or a pasted GitHub code-scanning alert JSON — holds up, tracing data flow, attacker control and impact through six gates to a per-finding TRUE or FALSE POSITIVE. Use when asked "is this real", "false positive?", which findings are exploitable, whether an alert can be closed, or to triage scanner results. Not for a CVE or advisory against a dependency or image — use vulnerability-triage-brocards:vulnerability-triage-brocards; not for hunting new bugs — use insecure-defaults:audit or static-analysis:semgrep.
argument-hint: "[findings file | path:line ...]"
allowed-tools: Read Glob Grep LSP Write Agent AskUserQuestion TaskCreate TaskUpdate TaskList TaskGet Bash(git log:*) Bash(git show:*) Bash(git blame:*) Bash(git rev-parse:*) Bash(grep -rn:*) Bash(printenv TMPDIR)
hooks:
  SubagentStop:
    - matcher: '^fp-check:(data-flow-analyzer|exploitability-verifier|poc-builder)$'
      hooks:
        - type: prompt
          timeout: 30
          prompt: >-
            An fp-check phase agent has stopped. Hook input JSON: $ARGUMENTS.
            If last_assistant_message holds no "Phase 1", "Phase 2" or "Phase 4" heading at all,
            the report was handed back another way; reply {"ok": true}.
            Otherwise check it for every heading that agent_type owes.
            fp-check:data-flow-analyzer: 1.1, 1.2, 1.3, 1.4 and a Phase 1 conclusion.
            fp-check:exploitability-verifier: 2.1, 2.2, 2.3, 2.4 and a Phase 2 conclusion.
            fp-check:poc-builder: 4.1, 4.2, 4.3, 4.4, 4.5 and a Phase 4 conclusion.
            A section holding an explicit N/A with a reason counts as present.
            All present: reply {"ok": true}.
            Some missing and stop_hook_active is false: reply
            {"ok": false, "reason": "missing sections: <list>; add them and stop again"}.
            Some missing and stop_hook_active is true: reply
            {"ok": false, "impossible": true, "reason": "still missing: <list>"}.
---

Findings: $ARGUMENTS

# fp-check

A scanner hit or a reviewer's note is a claim, not a fact. Here every claim gets traced through
the code until it either survives six gates (TRUE POSITIVE) or fails one of them (FALSE
POSITIVE). The burden sits on the evidence: a pattern that *looks* dangerous, or the same
pattern being exploitable somewhere else, decides nothing.

Dispatched as `fp-check:data-flow-analyzer`, `fp-check:exploitability-verifier` or
`fp-check:poc-builder`? Follow your agent brief and read only your section of
[phase-procedures.md](references/phase-procedures.md).

## Hard limits

- **The repository stays as it is.** No Edit, no Write inside it, no checkout. Older code is
  read with `git show --no-ext-diff --no-textconv <ref>:<path>`.
- **Write only PoCs**, and only under `$TMPDIR/fp-check-<repo>/bug-<N>/`. Resolve the absolute
  directory once: `printenv TMPDIR` for the base, `git rev-parse --show-toplevel` for `<repo>`.
  No placeholders in a PoC: concrete values only.
- **Nothing runs without a yes** (see "Running a PoC"). Never against a real host, service,
  cloud API, secret store or code host.
- **`git log` and `git show` stay read-only:** no `--output`, `--ext-diff` or `--textconv`.
- **No `gh`, no network.** A code-scanning alert is read from the user's paste, never fetched.
- **Nothing is posted, dismissed, commented or pushed.** Suggest a dismissal reason in words.
- **Secrets by location.** Quote a secret as `<redacted>` and give its `path:line`.
- **No installs.** A missing toolchain makes a PoC "written, not run", nothing more.
- **No fixes.** This marketplace has no security-fix skill. Asked to fix, say so and offer the
  verdicts and the fix direction; never claim a fix was made.

## Wrong door?

| The request | Where it belongs |
|---|---|
| CVE, advisory, Dependabot alert, `govulncheck` or Trivy result on a dependency or image | `vulnerability-triage-brocards:vulnerability-triage-brocards` — say so and run no phases |
| "find security bugs" in a service, even with a findings file lying around | `insecure-defaults:audit` or `static-analysis:semgrep` |
| A PR, branch or commit range | `differential-review:differential-review` |
| Go correctness or idiom; Ansible role conformance | `golang:review`; `ansible:role-checker` |
| Style or performance | an ordinary review |

A findings file in the tree does not make a hunt into triage. Only "which of these are real"
does.

## Reading the input

Accepted: SARIF; gosec, semgrep or bandit style lists; any findings file with `path:line`; a
finding from `insecure-defaults:audit`, `differential-review:differential-review`,
`sharp-edges:sharp-edges` or a person; a pasted GitHub code-scanning alert JSON. Code, secret,
IaC and CI findings all qualify as long as they point at a location.

For alert JSON, map the fields straight into the Step 0 record:

| JSON field | Becomes |
|---|---|
| `rule.id`, `rule.description` | bug class |
| `most_recent_instance.location.path` + `start_line` | location |
| `most_recent_instance.message.text` | the claim |
| `rule.severity`, `security_severity_level` | nothing — severity is the tool's opinion, not evidence |

Given only an alert URL or number, ask the user to copy the alert JSON from the alert page and
paste it. Do not try to fetch it.

Number the findings `BUG #1..N` in input order. If a claim cannot be restated as a coherent
sentence, ask: a few numbered questions, nothing else.

## Order of work

1. Step 0 for every bug first. Incoherent claims often collapse here, before any tracing.
2. Look up the class extras in [bug-classes.md](references/bug-classes.md).
3. Route each bug on its own: standard or deep.
4. Finish all standard bugs, then the deep ones.
5. With more than one bug, look for exploit chains (below).
6. Completeness check, then the final summary.

## Step 0 — restate the claim

Write this record per bug before opening anything else:

```text
BUG #N — Step 0
Claim:            <what is supposedly wrong, in one sentence>
Root cause:       <the defect that would cause it>
Trigger:          <the input or event that sets it off>
Impact:           <what the attacker gains if true>
Threat model:     <privilege of the code, sandboxing, what the attacker already holds>
Class:            <injection, auth, race, integer, crypto, ...>
Execution context:<how this code is reached: route, job, CLI, init>
Callers:          <who calls it and what they guarantee>
Architecture:     <layers the data crosses>
History:          <git log/blame of the area: recent fixes, reverts, TODOs>
```

## Standard or deep

Go **standard** when the claim is specific, sits in one component, belongs to a well-known
class, needs no concurrency and has a short source-to-sink path. Go **deep** when any of these
hold: the claim is vague, the path crosses three or more modules or services, the trigger is a
race, TOCTOU or async, it is a logic bug with no spec to compare against, a standard pass ended
inconclusive, or the user asked for full verification. Start standard by default; two
checkpoints can push a bug to deep.

## Standard path

One pass per bug, notes inline, no task tracking. Apply
[evidence-rules.md](references/evidence-rules.md) throughout.

- **S1 Data flow.** Find the sink, walk back to every source, at least two caller levels up.
  Note each trust boundary, every validation between source and sink, API contracts that
  already rule the class out, and environment protections that block it entirely. Add the
  class extras.
  *Checkpoint A:* three or more trust boundaries, callbacks or async hops, or a validation
  chain you cannot settle → go deep.
- **S2 Exploitability.** Who is the attacker, and how much of the value do they control (full,
  partial, none)? A value set by a trusted component is not attacker-controlled. Integer or
  bounds claims get an algebraic proof; race claims get a feasibility proof.
- **S3 Impact.** A real security consequence, or only robustness? Is this the primary
  control, or one layer of defence in depth while the primary one holds?
- **S4 PoC.** Pseudocode at minimum: source → validation → transform → sink → impact, with what
  the attacker controls and how it fires. Executable or unit-test PoCs are optional here.
- **S5 Devil's advocate.** The seven spot-check questions in
  [devils-advocate.md](references/devils-advocate.md); re-read the code after concluding.
  *Checkpoint B:* any doubt you cannot resolve → go deep.
- **S6 Gate review.**

On escalation, carry every note across. The deep path resumes; it does not redo S1–S5 work.

## Deep path

Per bug, a tracked task graph with blocking edges, three agents for phases 1, 2 and 4, and
phases 3, 5 and the gate review done by you. The graph, task titles, what to pass each agent
and the failure rules are in [deep-path.md](references/deep-path.md). Dispatch only
`fp-check:data-flow-analyzer`, `fp-check:exploitability-verifier` and `fp-check:poc-builder`,
by those full names, at most five agents at once.

## Gate review

All six must pass for TRUE POSITIVE. One failure makes it FALSE POSITIVE.

| Gate | Passes when |
|---|---|
| G1 Process | every step or phase of the bug's route left concrete evidence |
| G2 Reachability | an attacker reaches the location and controls the data; the PoC agrees |
| G3 Real impact | RCE, privilege escalation or information disclosure, with a concrete scenario; robustness alone fails |
| G4 PoC validation | the PoC shows attacker control, the trigger and the impact |
| G5 Math bounds | the vulnerable condition is arithmetically possible (non-arithmetic classes pass with "N/A — <why>") |
| G6 Environment | nothing in the environment blocks exploitation entirely; bar-raisers do not fail it |

Show the table filled in for every bug, one line of evidence per gate with `path:line`.

## Running a PoC

Writing a PoC never needs permission; running one does. Before any `go run`, `go test`,
`pytest`, interpreter or curl against a local build, ask with AskUserQuestion and name the
exact command. A unit-test PoC runs only in a throwaway local clone under the PoC directory,
never in the working tree. No yes, or no way to ask → print the command and mark the PoC
"written, not run". Never point a PoC at anything but local code.

## Exploit chains

With several bugs, revisit the rejected ones together: can two FALSE POSITIVES combine (a
leak that feeds a bypass, a write that enables an injection)? A viable chain is reported as
its own TRUE POSITIVE with both locations; the parts keep their verdicts.

## Before the summary

- [ ] every bug has a Step 0 record;
- [ ] every bug has each step of its route (S1–S6, or every deep task completed with evidence);
- [ ] every bug has a six-gate table;
- [ ] chains were considered when there was more than one bug.

## Output

Per bug, after its gate table:

```text
BUG #2 FALSE POSITIVE — df runs with constant arguments and no shell
    Gate 2 (Reachability) FAIL: no request data reaches exec.Command at cmd/agent/usage.go:41
```

or `BUG #1 TRUE POSITIVE — <short description>`. A FALSE POSITIVE names each failed gate and
the deciding evidence (the validation line and what it guarantees).

The final summary closes the last message:

```text
Summary: 1 TRUE POSITIVE, 1 FALSE POSITIVE
TRUE POSITIVE
  BUG #1 api/export.go:58 — query parameter reaches sh -c unescaped
FALSE POSITIVE
  BUG #2 cmd/agent/usage.go:41 — constant arguments, no shell
PoCs: $TMPDIR/fp-check-<repo>/  (written, not run)
```

If anything is added after it, repeat the whole summary so the last message stands alone.
For a code-scanning alert, add the dismissal reason you would pick ("false positive", "used in
tests", "won't fix") in words only.
