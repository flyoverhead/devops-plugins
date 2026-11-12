# Attack modelling for HIGH changes

Used by step 7 and 8 of the skill, and by `differential-review:adversarial-modeler`, which gets
one change and returns one finding.

## Contents

- Deep context
- The five steps
- Attacker models
- Exploitability
- Finding template
- Worked example
- When the answer is "not exploitable"

## Deep context

Before modelling, know what the changed code is for.

1. **Flow.** Entry guards (auth, validation, feature flags), state read and written, external
   calls (network, disk, subprocess, secret store), what it returns and to whom.
2. **Call graph inward.** From the changed line, follow callers until the first trust boundary:
   an HTTP handler, a CLI argument, a message consumer, a CI trigger, a role variable set by an
   inventory.
3. **Boundaries and assumptions.** Which inputs come from outside; what the code assumes about
   them (length, charset, already authenticated, already validated by the caller).
4. **Invariants.** Write the property that held before ("the store's certificate chains to the
   pinned CA") and check whether it still holds after.
5. **Five whys.** Why was it changed? Why did the old code exist? Why might the new code break?
   Why this approach and not another? Why would it fail in production rather than in tests?
6. **Neighbour check.** Grep for siblings of a removed `validate` / `verify` / `auth` /
   `require` / `assert` / `no_log` line. A boundary that now has one check fewer than the
   others of its kind is a finding of its own.

## The five steps

Write each part down, in this order.

1. **What it undoes.** The guarantee that held on the base side and fails now: an invariant, a
   trust boundary, a validation habit the rest of the code keeps, or an earlier fix. Point at
   it as `path:line @ <base sha>` or by commit.
2. **Adversary.** Pick a model from the list below; state the access it starts with and the
   entry point it uses.
3. **Route.** The hops from that entry point down to the changed line, one `path:line` each.
   If one hop cannot be shown, there is no route.
4. **Walk-through.** Where the adversary starts, the numbered actions with actual values, and
   an outcome someone could measure (data read, command run, money moved, host reached).
5. **Difficulty.** EASY, MEDIUM or HARD, and the reason for the rating.

## Attacker models

| Model | Typical entry |
|---|---|
| Unauthenticated network client | public HTTP endpoint, open port |
| Authenticated user | API with a valid session, another tenant's IDs |
| Contributor with push to a branch, not to main | branch pipelines, PR builds |
| Fork PR author | `pull_request_target`, fork MR pipelines |
| Compromised dependency or image | package update, mutable image tag, unpinned action |
| Compromised job elsewhere | a CI job or service sharing runners, caches or credentials |
| Host on the same network segment | traffic between the service and its backends |

## Exploitability

| Rating | Meaning |
|---|---|
| EASY | Public interface or ordinary developer access; one step |
| MEDIUM | Several steps, timing, or a role or state that can be obtained (a network position, a branch) |
| HARD | Admin-level access, a rare condition, or heavy resources |

## Finding template

````markdown
### <SEVERITY>: <title>

- **Location:** `path:line`, commit `<sha>`
- **Attacker:** <model, access, entry point>
- **Exploitability:** <EASY | MEDIUM | HARD>, <reason>
- **Blast radius:** <N> callers or consumers (<how counted>)
- **Tests:** <yes | no | partial>
- **Change:** <before> → <after>
- **Attack:**
  1. <step with values>
  2. <step>
- **Impact:** <concrete result>
- **Fix:**

```<language>
<the specific change>
```
````

Severity words: CRITICAL, HIGH, MEDIUM, LOW. Secrets in any field are `<redacted>`.

## Worked example

A Python reporting service calls a billing API. Commit `4be19d0` ("fix(security): verify
billing API certificate against the bundled chain") had set `verify=CA_BUNDLE`. The change under
review replaces that with a switch:

```python
# billing/client.py:14 (after)
VERIFY = not os.environ.get("BILLING_TLS_INSECURE")
session.verify = VERIFY
```

The Helm values in the same diff set `BILLING_TLS_INSECURE: "no"`. `os.environ.get` returns the
string `"no"`, which is truthy, so `VERIFY` is `False`.

````markdown
### CRITICAL: billing API calls accept any certificate

- **Location:** `billing/client.py:14`, commit `9e07a2c`; regression of `4be19d0`
- **Attacker:** host on the same network segment as the service; no credentials needed
- **Exploitability:** MEDIUM, needs a network position (ARP or DNS spoofing on the segment)
- **Blast radius:** 7 callers of `billing.client.session` in this repository
- **Tests:** no; `tests/test_client.py` never sets the variable
- **Change:** `session.verify = CA_BUNDLE` → `session.verify = not os.environ.get("BILLING_TLS_INSECURE")`; `deploy/values.yaml:9` sets it to `"no"`
- **Attack:**
  1. Answer the service's DNS query for the billing host with your own address.
  2. Present a self-signed certificate; `requests` accepts it because `verify` is `False`.
  3. Read the `Authorization: Bearer <redacted>` header from the first call and replay it.
- **Impact:** the billing API key is captured; invoices can be read and created with it.
- **Fix:**

```python
CA_BUNDLE = Path(__file__).with_name("billing-ca.pem")
session.verify = str(CA_BUNDLE)
```

Delete `BILLING_TLS_INSECURE` from the code and from `deploy/values.yaml`.
````

`git log -S'verify=CA_BUNDLE' --oneline` gave both commits: `4be19d0` adding the pin and
`9e07a2c` removing it. That pair is what makes it a regression, and why it is CRITICAL rather
than HIGH.

## When the answer is "not exploitable"

If no entry point reaches the changed line (dead code, a test-only path, a flag that nothing
can set), the finding is "not exploitable as written". Say which hop is missing, keep the
severity no higher than LOW, and note what future change would make it reachable.
