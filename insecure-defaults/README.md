# insecure-defaults

Finds configuration that is unsafe when nobody sets it, then tries to disprove each hit before
reporting it. Static and read-only: it greps and reads, never runs the code or its tooling, and
never prints a secret value.

```text
/plugin install insecure-defaults@devops
```

## What it covers

| Category | Examples |
|---|---|
| Secrets with literal fallbacks | `os.getenv("KEY", "literal")`, `${KEY:-literal}`, Terraform `variable` with a secret default, `secrets.X \|\| 'literal'` |
| Shipped credentials | admin/admin seeds, DSNs with passwords, placeholder passwords in role defaults, Compose literals |
| Checks that fail open | `verify=False`, `InsecureSkipVerify`, `validate_certs: false`, `curl -k`, `continue-on-error` on a scan |
| Broken or misused crypto | MD5/SHA-1 for passwords or signatures, DES/RC4/ECB, JWT `none`, `math/rand` tokens |
| Over-broad access | `*` CORS, `0.0.0.0/0`, mode 0777, public ACLs, privileged pods, `pull_request_target` with PR checkout, unpinned actions |
| Debug surfaces left on | debug on by default, pprof on a public port, stack traces to clients, `set -x` near secrets, Ansible tasks writing secrets without `no_log`/`diff: false` |

Stacks: Go, Python, Bash, TypeScript/JavaScript, Terraform, Ansible, GitHub Actions workflows
and local composite actions.

## Usage

```text
/insecure-defaults:audit                 # current directory
/insecure-defaults:audit services/api    # a directory
/insecure-defaults:audit cmd/server/main.go
```

Or ask in plain words: "audit this role for insecure defaults", "what happens if
`SESSION_KEY` is not set?".

## How a hit becomes a finding

1. **Recon:** checks the path exists, detects the stack, finds config accessors that can return
   a default, and lists deploy manifests (Helm values, tfvars, inventories, Compose, CI files).
2. **Discover:** per category, loads that category's seed and example files and runs each seed
   as its own `grep -rnE`, plus patterns derived for the stack.
3. **Verify:** every candidate starts as refuted. It is confirmed only if it reaches production,
   the insecure value actually executes, the value is insecure, a security sink uses it, and
   (for configurable values) the deployment can leave it unset. Large audits hand batches of
   up to 16 candidates to the `default-verifier` agent, five at a time.
4. **Report:** summary, findings with `file:line` and sink, remediation grouped by fix,
   coverage and limits (what was not searched or not verified, commands worth running by
   hand), and a table of refuted candidates with the step that refuted each.

## Not this plugin

| Need | Use |
|---|---|
| Secrets in git history | gitleaks as a pre-commit hook or in CI |
| Verdicts on scanner or code-scanning alerts | `fp-check:fp-check` |
| Go review | `golang:review` |
| Ansible role structure | `ansible:role-checker` |
| Fixed-pattern scans | `static-analysis:semgrep` |
| Misuse-prone API design | `sharp-edges:sharp-edges` |
| Reviewing a PR or commit range | `differential-review:differential-review` |

## Required tools

None beyond `grep` (POSIX ERE). Nothing is installed.

## Tests

```bash
python3 -m pytest insecure-defaults/tests -q
```

The corpus test checks that the category table, seed files and example files agree, that
every vulnerable example is matched by a seed, and that every seed matches an example.
