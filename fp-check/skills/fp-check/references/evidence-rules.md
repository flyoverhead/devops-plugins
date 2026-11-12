# Evidence rules

What counts as proof, and what does not, on both the standard and the deep path.

## Contents

- What is never evidence
- Who controls the data
- Protections and contracts
- Arithmetic and bounds
- Concurrency
- Impact
- The thirteen checks
- Red flags
- Your own bias

## What is never evidence

- "It looks dangerous." A verdict needs a traced path.
- The same pattern being exploitable in another project or another file.
- The scanner's severity, confidence or CWE tag.
- A clean static-analysis run, for logic and auth bugs.
- A mitigation you assume exists but have not read. Open the file and cite the line.

Trace at least two caller levels above the sink. Upstream conditions (a length check, an enum
switch, a guard that returns early) often make the flagged state unreachable.

## Who controls the data

| Source | Default trust |
|---|---|
| Request bodies, query strings, headers, sockets, message queues | untrusted |
| File contents, uploads, archives | untrusted unless only a privileged party writes them |
| Environment variables | untrusted where an attacker can set them (CI from forks, shared runners) |
| Database rows | untrusted when users can write them; find the writer first |
| Constants, values set by privileged init, config only operators write | trusted |

Before calling stored data attacker-controlled, find what writes it and who can reach that
writer. Grade control as **full**, **partial** (inside constraints: charset, length, format)
or **none**.

## Protections and contracts

Split every protection into two kinds; only the first can produce a FALSE POSITIVE:

- **Prevents entirely:** parameterised queries, a safe-subset language, no shell in the call
  path, a type system that rules the value out.
- **Raises the bar:** ASLR, stack canaries, CFI, WAF rules, rate limits.

Contracts that remove a class outright, once you confirm they are in use and not bypassed:

- Go `exec.Command(name, args...)` with no shell — no shell injection (argument injection into
  the program itself is still possible; check the program);
- `database/sql` placeholders and ORM bind parameters — no SQL injection through the values;
- Go `html/template` and framework auto-escaping — no XSS in the escaped context (check that
  escaping is on and nothing marks the value safe);
- Ansible `command` module — no shell parsing (unlike `shell`).

Memory corruption claimed in Go without `unsafe` or cgo, in safe Rust, or in a managed
runtime is almost always false. Prove the unsafe block or the native call first.

## Arithmetic and bounds

For integer, length, index and allocation claims:

1. List every variable on the path with its width and signedness.
2. List every constraint applied to them, each with `path:line`.
3. Derive, step by step: if the constraints hold, does the vulnerable condition still occur?
4. Give a concrete triggering value when one exists.

Signed overflow is undefined behaviour in C and C++; unsigned arithmetic wraps; Go wraps
silently for both. Keep three outcomes apart: **impossible by arithmetic**, **infeasible in
practice** (needs 2^60 requests), and **feasible**. Only the first fails G5 outright.

## Concurrency

A race needs proven concurrent access to the same state: two goroutines, threads, requests or
processes that really run at once. Single-threaded init and accesses already under a lock
fail the claim. For a real race, estimate the window and whether the attacker can widen it
(slow filesystem, large input, many parallel requests). For filesystem TOCTOU, check the
attacker can change the path between check and use.

## Impact

- A real security consequence: code execution, privilege gain, data exposure across a trust
  boundary.
- Not one: a crash the supervisor restarts, a log line, a slower response, unless the class
  rules (DoS amplification) make it one.
- A failing defence-in-depth layer is not a vulnerability while the primary control holds.
  Name the primary control and show it holding.

## The thirteen checks

Run every bug through all of them and note the answer to each in your working notes.

1. Have you followed the whole validation chain, not just the line flagged?
2. Do conditional branches upstream guarantee a value (minimum length, non-nil, enum)?
3. Is the flagged code a defensive assertion rather than a flaw?
4. Is every hop of the data path confirmed by reading code, not assumed?
5. What is the trust context of the source?
6. Do the bounds of related values (length vs buffer size) already exclude the bad case?
7. For TOCTOU: can the checked value actually change in between?
8. Does an API contract already prevent the class?
9. Is this internal storage written by trusted code, mistaken for external input?
10. Is the verdict based on analysis, or on a pattern match?
11. Can the concurrency really happen in this program?
12. Is the impact real or theoretical?
13. Is this defence in depth with the primary control still in place?

## Red flags

Slow down when you notice any of these in your own reasoning:

- the flagged line *is* the validation code;
- an upstream check was skipped over;
- network data is assumed to reach the sink without a traced hop;
- the path is test-only, debug-only or runs only at install time;
- an off-by-one claim with no look at the loop bounds;
- an API was read from memory instead of from its contract.

## Your own bias

Assume you lean toward seeing bugs and toward rating them high. Equally, do not dismiss a
real bug because the exploit is fiddly, and do not invent a mitigation to close a finding.
After reaching a verdict, re-read the sink and its callers once more.
