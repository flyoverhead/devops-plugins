# Verdicts, evidence and severity

## Contents

- [The six verdicts](#the-six-verdicts)
- [What counts as evidence](#what-counts-as-evidence)
- [Earning absent](#earning-absent)
- [Refuter outcomes](#refuter-outcomes)
- [Severity](#severity)
- [Reading the results](#reading-the-results)

## The six verdicts

| Verdict | Use it when | It must carry |
|---|---|---|
| `implemented` | the enforcing code was found, opened and read, and it holds on every path | the enforcing lines and the paths walked |
| `partial` | it holds on some paths and not others | each failing path, named, with `path:line` |
| `contradicted` | the code does something incompatible with the document | the conflicting lines next to the quote |
| `stronger-than-spec` | the code enforces an extra constraint the document does not state | the extra check and the sentence it goes beyond |
| `absent` | nothing enforces it anywhere it could plausibly live | the search log (see [Earning absent](#earning-absent)) |
| `undecidable` | the requirement is too vague to test | why it cannot be tested; this is a finding against the document |

Pick between neighbours deliberately and write down why: `partial` versus `contradicted` is
"some paths comply" versus "no path does"; `absent` versus `partial` is "nothing enforces it"
versus "something does, but not everywhere".

## What counts as evidence

- **A name proves nothing.** `checkQuota(...)` counts only after you open `checkQuota` and see
  it compare against the document's bound on every path through it. Callers can satisfy what
  a callee ignores, so read the callers too.
- **Arithmetic is evidence.** `idle = 1800` with `time.Second` is 30 minutes;
  `retainDays * 24` hours with `retainDays = 7` is a week. Verify the value, not the vocabulary. Then check three more things: the constant
  cannot be overridden (env, flag, config), every issuing path uses it, and the verifier
  rejects what is past the bound.
- **Walk every path**, not only the success path: error branches, early returns, alternate
  roles or tenants, retries, defaults when a header or variable is unset.
- **Judge only the requirement at hand.** Other problems get one line under Open questions.
  "Systems like this usually do X" is not evidence.
- **Cite everything.** Code as `path:line` or `path:L10-L24`; the document verbatim. What
  cannot be cited becomes an explicit "could not establish …" and lowers confidence. No
  "probably", "seems", "likely".

## Earning absent

`absent` is a claim about everywhere, so it rests on a written search log. Each entry is
`pattern or symbol -> where -> result`, for example:

```text
"MaxBody|LimitReader|maxBytes" -> **/*.go -> 3 hits, all in tests
"argument_specs" required for app_admin_pass -> meta/argument_specs.yml -> key present, no required: true
"validation" -> variables.tf, validate.tf -> 0 hits
```

Vary the vocabulary: rate limit / limiter / throttle / quota / `x/time/rate`;
required / `argument_specs` / assert / fail / validation. Then look where enforcement hides
for that stack (see `sources.md`): middleware, wrappers, included task files,
`validate.tf`, `rules:`, callers. The verdict explains why the searches were exhaustive,
not merely unsuccessful.

## Refuter outcomes

| Refuter says | Result |
|---|---|
| `refuted: yes` (either lens) | drop the divergence; list it under Refuted with the refuter's evidence |
| `refuted: no`, `revisedVerdict: <v>` | keep it with the revised verdict |
| `refuted: no`, `correction: <text>` | keep it, described as corrected |
| `refuted: no`, nothing else | keep it as the checker described it |
| both refuters failed | Unverified, not a finding |

The orchestrator never overrules a refuter.

## Severity

Severity is about consequence, not about how differently the code and document are worded.

| Severity | When |
|---|---|
| critical | an untrusted actor can move data, secrets or control in a way the document rules out: a required access check missing on a reachable path, a secret written to logs, TLS verification off by default |
| high | the same, but it needs a privilege or a precondition first; or enforcement exists on the tested paths and is missing on another reachable one |
| medium | a real gap whose consequence is not established: a path that is unreachable today but could become reachable, an ambiguity that made two components behave differently |
| low | no behavioural consequence: the document is wrong, or the code is stronger than the spec; the fix belongs in the document |

Raise it for: reach by an untrusted actor, no unusual state needed, runs on every call,
mandatory wording, other components depending on the guarantee. Lower it for: needs a role
only the owner holds, a second mechanism enforces the same thing, the path is unreachable
for a stated reason. How emphatically the document words it neither raises nor lowers.

State a consequence only when you can show it: who acts, in what order, what happens.
Otherwise write what would have to be true for it to matter. No invented attack chains,
no invented numbers.

Standards: an omitted SHOULD is a documented deviation, not a defect.

## Reading the results

- `partial` is usually the most serious: it survives testing because the tested path passes.
- `absent` is only as good as its search log.
- `undecidable` and any `documentProblem` are findings against the document.
- `stronger-than-spec` is low today and a regression risk later: the next refactor will
  "fix" the code back to the document.
