# Phase procedures

One section per delegated phase. Each agent reads only its own section; the skill reads them
to know what comes back. Every claim in a report carries `path:line`. Words such as "probably"
or "likely" do not appear; what could not be settled is stated as such.

## Contents

- Phase 1 — data flow (`fp-check:data-flow-analyzer`)
- Phase 2 — exploitability (`fp-check:exploitability-verifier`)
- Phase 4 — proofs of concept (`fp-check:poc-builder`)

## Phase 1 — data flow

**Given:** the claim (what, root cause, trigger, impact), the class, the alleged `path:line`,
the repository root, any notes from a standard-path S1, and the Step 0 `History:` field.

**Method:**

1. Pin down the sink: the exact call or statement where harm would occur.
2. Walk backwards to every source that feeds it. Label each source trusted or untrusted using
   the evidence rules; for stored data, find the code that writes it.
3. At every hop, record any validation: its condition, its line, and whether the attacker's
   value passes it, fails it, or can bypass it.
4. Climb at least two caller levels above the sink and note what each caller guarantees.
5. For each API on the path, does it carry a built-in protection (no shell, bound parameters,
   auto-escaping)? Does that hold for the version and configuration in use?
6. List environment protections and classify each: prevents entirely, or raises the bar. Add
   a note on language safety (memory-safe language, `unsafe` or cgo present).
7. Cross-reference: similar code elsewhere, tests touching the path, TODO or review notes.
   The agent has no git access, so 1.4 History reuses the Step 0 `History:` field passed in
   the context; say so in the report, and say "not provided" when it is absent.

**Report:**

```text
## Phase 1 — Bug #N

### 1.1 Trust boundaries and path
Source: <what> — <trusted|untrusted> — <path:line>
Path: <path:line> → <path:line> → ... → sink <path:line>
Validation: <condition> at <path:line> — <passes|fails|bypassable>: <why>
Callers: <caller path:line> guarantees <what>; <caller path:line> guarantees <what>

### 1.2 API contracts
<API> — <has|lacks> protection: <which> — applies to version/config in use: <yes|no, why>

### 1.3 Environment protections
<protection> — <prevents entirely|raises the bar> — <evidence>
Language safety: <note>

### 1.4 Cross-references
Similar patterns: <path:line ... or none found>
Tests: <test files covering the path, or none>
History: <relevant commits, blame, TODOs>

### Phase 1 conclusion
<data reaches the sink with attacker control | data is validated before the sink |
attacker cannot control the data here> — <decisive path:line>
```

## Phase 2 — exploitability

**Given:** the claim and the complete Phase 1 report.

**Method:**

1. **Attacker control (2.1).** Name the attacker concretely: an unauthenticated client, a
   logged-in user, someone with push access, a job on a shared runner, a host on the same
   network. Give the entry point, the control level (full, partial, none) and everything
   that shapes the value on the way: encoding, normalisation, truncation, type coercion.
2. **Bounds (2.2).** For arithmetic or size claims, the algebra from the evidence rules: each
   variable with width and signedness, each constraint with `path:line`, the derivation, a
   triggering value when one exists. Otherwise `N/A — not a bounds issue`.
3. **Race (2.3).** For concurrency claims: threading model, window size, whether the attacker
   can widen it, the synchronisation in place, and for filesystem TOCTOU whether the attacker
   controls the path. Otherwise `N/A — not a concurrency issue`.
4. **Synthesis (2.4).** Combine the three into one attack scenario, or show where it breaks.

**Report:**

```text
## Phase 2 — Bug #N

### 2.1 Attacker control
Attacker: <concrete actor>
Entry point: <how the value enters> — <path:line>
Control: <full|partial|none>; constraints: <encoding, length, charset ...>
Reachable: <yes|no> — <path:line>

### 2.2 Bounds proof
<derivation, or N/A — not a bounds issue>

### 2.3 Race feasibility
<analysis, or N/A — not a concurrency issue>

### 2.4 Adversarial synthesis
Scenario: <step by step>
Attacker needs: <capabilities>
Feasibility: <feasible | infeasible | conditional on X>

### Phase 2 conclusion
<exploitable | not exploitable> — <reason with path:line>
```

## Phase 4 — proofs of concept

**Given:** the claim, the Phase 1–3 results, the language and build system, and the absolute
PoC directory `$TMPDIR/fp-check-<repo>/bug-<N>/`. Only bugs that passed phases 1–3 get here.

**Rules:**

- Write files only inside the given PoC directory. Never inside the repository.
- Run nothing. Each PoC comes with the exact command and the expected output; the skill asks
  the user before anything runs.
- Concrete values everywhere: real parameter names, real payloads, real ports from the code.
- Skip an executable PoC, with the reason, when it needs special hardware or network, the
  runtime is absent, it would require changing production code, the target is closed
  source, or it would touch a real host, service, cloud API, secret store or code host.
- A unit-test PoC follows the repository's test style (`*_test.go` tables, pytest
  functions) and is meant to run in a throwaway local clone, never the working tree.

**Report:**

```text
## Phase 4 — Bug #N

### 4.1 Pseudocode PoC
<source → validation → transform → sink → impact, with the attacker's concrete values,
path:line for each hop and why each check lets the value through>

### 4.2 Executable PoC
Status: <written: path | skipped: reason>
Command: <exact command>
Expected output: <what proves impact>

### 4.3 Unit-test PoC
Status: <written: path | skipped: reason>
Command: <exact command, run inside a throwaway clone>
Expected output: <failing or passing assertion that proves impact>

### 4.4 Negative PoC
Benign input: <value> → <behaviour>
Preconditions for the exploit: <list> — how the attacker forces each: <...>
Exploit input: <value> → <behaviour>

### 4.5 Verification
- pseudocode matches the traced path: <yes|no>
- executable PoC shows impact: skipped — not run by this agent
- unit-test PoC passes: skipped — not run by this agent
- preconditions realistic: <yes|no, why>
- artificial bypasses (mocks, disabled checks, patched code): <none | list — invalidates the PoC>

### Phase 4 conclusion
<demonstrates the vulnerability | could not demonstrate> — <reason>
```
