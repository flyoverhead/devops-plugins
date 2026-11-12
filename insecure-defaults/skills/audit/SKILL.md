---
name: audit
description: Hunts insecure defaults in Go, Python, Bash, TypeScript, Terraform, Ansible and GitHub Actions — fallback secrets, shipped passwords, fail-open checks, weak crypto, wide access, debug left on — keeping a hit only once traced to a security sink. Use when asked what runs if a setting is missing, or for hardcoded secrets or a config-defaults review. Not for git history — use gitleaks; not for scanner alerts — use fp-check:fp-check; not for Go review — use golang:review; not for role lint — use ansible:role-checker; not for fixed patterns — use static-analysis:semgrep; not for API footguns — use sharp-edges:sharp-edges; not for PRs — use differential-review:differential-review.
argument-hint: "[path]"
allowed-tools: Read Glob Grep Bash(grep -rnE:*) Bash(grep -Ec:*) Bash(test -e:*) Agent TaskCreate TaskUpdate TaskList
---

Target: $ARGUMENTS

# Insecure-defaults audit

Find configuration that is unsafe when nobody sets it, then try to knock each hit down. A hit
becomes a finding only when you can cite the line where the value controls a security decision
and show that a real deployment can run with it.

**Running as `insecure-defaults:default-verifier`?** Ignore everything below. Your agent brief
is the whole job.

## Hard limits

- **Look, never run.** No `ansible-playbook` (check mode and localhost included), `ansible`,
  `terraform`, `tofu`, `helm`, `kubectl`, `docker`, `go run`, `go test`, `python`, `node`,
  `npm`, `act`, `gh workflow run`, and none of the target's own scripts. Do not write a scratch
  program or playbook to "see what happens". A claim that only a run can settle goes under
  **Worth a manual check** with the command for the user.
- **Change nothing.** No edits, no new files in the repository. The report is your answer in
  chat.
- **No secret values in output.** Quote the offending line with the value replaced by
  `<redacted>` and give `file:line`. Placeholder names such as `CHANGE_ME` may be quoted.
  Recommend a secret manager for anything real.
- **No network.** Nothing is fetched, installed or called; workflows are read from the local
  tree.
- **A partial run must read as partial.** No candidates means no matches for the patterns that
  ran, not proof of absence.

## Categories

Each category has two files under `references/`: `<id>.json` (POSIX ERE seeds) and `<id>.md`
(what to report, what to skip, vulnerable and secure examples).

| Id | Title | Typical hit |
|---|---|---|
| `fallback-secrets` | Secrets with literal fallbacks | key or password replaced by a literal when its setting is unset |
| `default-credentials` | Shipped credentials | username/password, token or DSN shipped in code or defaults |
| `fail-open-security` | Checks that fail open | TLS, auth, CSRF or a CI gate off by default or ignored on failure |
| `weak-crypto` | Broken or misused crypto | MD5/SHA-1 for secrets, DES/RC4/ECB, JWT `none`, non-crypto RNG for tokens |
| `permissive-access` | Over-broad access | `*` origins, `0.0.0.0/0`, mode 0777, public ACLs, broad CI token or trigger |
| `debug-features` | Debug surfaces left on | debug on, profilers, introspection, stack traces, secrets in diffs or traces |

## Procedure

Create four tasks (Recon, Discover, Verify, Report) and tick each when done.

### 1. Recon

1. Target is the argument, or `.` when empty. Run `test -e <target>` first. If it fails, stop
   and say the path does not exist. Never produce a report for a missing path.
2. **Profile the stack.** Glob for extensions (`go`, `py`, `sh`, `ts`/`js`, `tf`, `yml`/`yaml`
   under `roles/`, `playbooks/`, `.github/workflows/`, `.github/actions/`). For a single file,
   profile only what it imports or calls (its config helpers, its wrapper module).
3. **Find the config accessors.** A project helper such as `config.Get(key, def)`, `envOr`,
   `settings.get` or a viper wrapper outranks raw `os.Getenv`. Mark each accessor that can
   hand back a default: that is where fail-open lives, and every call to it is a candidate site.
4. **List deploy manifests.** Anything that feeds real values in production answers step 5
   later. Look for:
   - Kubernetes: chart `values*.yaml` and plain manifests;
   - containers: compose files (`docker-compose*.yml`) and `ENV` lines in Dockerfiles;
   - Terraform `*.tfvars`; Ansible inventories with their `group_vars/` and `host_vars/`;
   - CI: `env:`, `vars.` and `secrets.` in `.github/workflows/*.yml` and `.gitlab-ci.yml`;
   - systemd unit files and references to secret-store paths.
5. **Exclusions** apply only outside the named target: `.git`, `vendor`, `node_modules`,
   `.terraform`, `molecule`, tests, fixtures, examples, docs, generated code, build output.
   If the user pointed at one of these, audit it.

### 2. Discover, one category at a time

For each category in table order:

1. Read `references/<id>.json` and `references/<id>.md`, and no other category's files. If
   either is missing, stop: the plugin is installed incompletely, and a category is never
   audited without its corpus.
2. Run every seed as its own call, never several joined with `|` or `-f` (the system grep may
   reject complex patterns):

   ```bash
   grep -rnE --exclude-dir=.git --exclude-dir=<each Recon exclusion> -e '<seed>' <target>
   ```

   Build the `--exclude-dir` list from the Recon exclusions (`vendor`, `node_modules`,
   `.terraform`, `molecule`, test, fixture, example and docs directories, build output), then
   drop every name that appears as a component of the target path. `--exclude-dir` also
   matches a directory named on the command line, so `audit vendor/lib` with
   `--exclude-dir=vendor` would search nothing and read as clean.

   Seeds contain `'`; write each one as `'\''` inside the single-quoted pattern. Keep to POSIX
   classes (`[[:space:]]`, `[0-9]`); `\s`, `\d` and `\b` fail silently on some builds. A grep
   that exits 2 is a failed search: report it, never count it as zero hits.
3. Derive extra patterns for this stack; seeds are the floor. Examples: calls to the accessors
   from Recon, framework setting keys, `default =` inside `variable` blocks, literals in
   `defaults/main.yml`, Bash `${VAR:-x}`, Go `flag.String` defaults, `${{ secrets.X || '…' }}`.
4. For workflows, absence matters too: `grep -Ec '^permissions:' <file>` returning 0 means the
   token inherits the repository default. Note job-level `permissions:` before reporting it.
5. Record each candidate as `category:file:line`, the snippet and the symbol involved. Do not
   judge yet; over-collect, including unconditional literals that no setting controls. The
   dedupe key is `category:file:line`, so a line two categories hit stays two candidates.
6. Per category note files scanned, seeds run and derived patterns run. Zero files scanned
   means the category did not run; it is never "clean".

### 3. Verify

Up to 16 candidates in total: verify them yourself. More than 16: dispatch
`insecure-defaults:default-verifier` agents, one per batch of at most 16 candidates from one
category, grouped by directory, no more than 5 running at once. Never use a general-purpose
agent. Hand every agent the same context you built in Recon (where the target is, what is
excluded, which manifests supply values), the path to this category's `.md` file, and its hits
as `path:line` with the category and the pattern that matched. Check that each hit returns a
row; list any that do not under **Not verified**.

The ladder: start from "refuted", walk the steps in order, stop at the first one that refutes,
and record its number. Confirm only with citable code.

| Step | Question | Refutes when |
|---|---|---|
| 1 | Does production reach this line? | excluded path, dead code, dev-only branch, script nothing packages or calls |
| 2 | Which value actually executes? | a lookup whose missing branch halts: raising read, fatal on empty, startup validator, Terraform `validation`, Ansible `assert`. A literal in code is unconditional and step 2 never refutes it |
| 3 | Is the value itself insecure? | the corpus **Skip when** line covers it (non-security hash, loopback, deliberate public asset) |
| 4 | Where is it enforced? | no sink: the value is read but never decides TLS verification, exposure, credential comparison, authn/authz, encryption or signing. Cite the sink `file:line` |
| 5 | Does deployment always supply it? | never refutes; sets severity for configurable values (below) |

Step 5 severity: always supplied → confirm at lowered severity; never supplied → CRITICAL,
production runs on the fallback; sometimes → full severity, name the manifests that leave it
unset; unknown → treat as reachable and name what could not be resolved.

Rules of thumb:

- A trace you cannot finish is "refuted: trace incomplete: <what blocked it>", listed so the
  user can follow it up.
- MD5 or SHA-1 for an ETag, cache key or checksum is refuted at step 3 or 4.
- Workflows: step 5 becomes "can a fork pull request reach it?" `pull_request_target`,
  `workflow_run` and fork-reachable jobs outrank push-to-protected-branch jobs; a protected
  environment with required reviewers lowers severity. Unpinned third-party actions and
  `${{ github.event.* }}` or `github.head_ref` inside `run:` are reported as found.

### 4. Report

Write the report in chat in this order. Group findings that share a root cause (one wrapper,
one defaults file) under one heading.

```markdown
## Summary
<n> findings: <c> critical, <h> high, <m> medium, <l> low. <x> configurable, <y> unconditional.
<one sentence on real exposure as deployed>

## Findings
### <SEVERITY> · <short title>
| Field | Content |
|---|---|
| Where | `path:line` |
| Line | the offending code, secret replaced by `<redacted>` |
| Enforced at | `path:line` of the sink, plus what the trace showed |
| Deployed as | which manifests leave it unset, or "unconditional: no setting can mitigate it" |
| Attack | how someone uses it, or why the deployed setup blocks that |

## Remediation
<grouped by fix, naming files>

## Coverage and limits
Target, files scanned, categories run, seeds vs derived patterns, candidates found vs refuted.
### Not searched
### Not verified
### Seeds only
### Worth a manual check
<claim> — run: `<exact command for the user>`

## Refuted
| Location | Step | Reason |
```

Remediation vocabulary: a required lookup that fails when unset (`os.LookupEnv` plus exit in Go,
`os.environ["X"]` in Python, `${X:?}` in Bash); a Terraform variable with no default, `sensitive`
and `validation`; an Ansible `assert` before first use; values from a secret manager instead of
literals; one startup validator for all settings; `no_log: true` and `diff: false` on tasks that
write secrets. For workflows: pin actions to a full commit SHA, set a minimal `permissions:`
block, pass event fields through `env:` and quote the variable, avoid checking out PR code
under `pull_request_target`.

Empty headings under Coverage and limits say "none". Never drop the section. Commands under
**Worth a manual check** are for the user to run; you never run them.

## Elsewhere

| Request | Go to |
|---|---|
| "Was a key ever committed?", history scans | gitleaks (pre-commit hook or CI secret scanning); nothing in this marketplace covers it |
| Verdicts on scanner output or a code-scanning alert | `fp-check:fp-check` |
| Go correctness or idiom | `golang:review` |
| Ansible role layout and lint | `ansible:role-checker` |
| A known fixed pattern across the repo | `static-analysis:semgrep` |
| Footgun APIs and dangerous interface design | `sharp-edges:sharp-edges` |
| Security review of a PR or commit range | `differential-review:differential-review` |
