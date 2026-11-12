---
name: sharp-edges
description: Probes the caller-facing surface of code — Go, Python and TypeScript APIs, CLI flags, env vars, Bash scripts, Ansible role variables, Terraform inputs, GitHub Actions and GitLab CI workflows — for spots where the default or shortest usage is insecure, backing each finding with a minimal misuse. Use when asked if an API, role, module or workflow is easy to misuse, for footguns, secure defaults or misuse resistance, or before other teams consume it. Not for unsafe values already in code — use insecure-defaults:audit; not for a PR or diff — use differential-review:differential-review; not for Go style — use golang:review; not for role layout — use ansible:role-checker.
argument-hint: "[path] [interface ...]"
allowed-tools: Read Glob Grep Bash(grep -rn:*) Bash(git ls-files:*) Bash(ls:*) Agent
---

Target: $ARGUMENTS

# Sharp edges

An interface has a sharp edge when the call a hurried person writes first, the example they
copy, or the setting they leave alone is the insecure one. Safe use has to be the path of least
effort. If staying safe depends on reading the documentation carefully, count that as a design
failure, not a user error.

**Dispatched as `sharp-edges:sharp-edges-analyzer`?** Follow your agent brief and use only the
parts below that it points to.

## Ground rules

- **Read-only.** Read, glob and grep. Edit nothing, create nothing in the repository; the
  report is your reply.
- **Execute nothing from the target:** no builds, tests, interpreters, `ansible*`,
  `terraform`, workflow runners or project scripts. A misuse is shown as code, not run.
- **No installs, no network.** `gh` is not used; a local path is all you need.
- **Secrets by location only.** Say where a plaintext secret sits (`path:line`); never repeat
  its value.

## Is this the right skill?

| The user wants | Send them to |
|---|---|
| Unsafe values already present: hardcoded or fallback secrets, switches set to off | `insecure-defaults:audit` |
| A review of a PR, a commit, a branch diff | `differential-review:differential-review` |
| Go idiom, style, correctness | `golang:review` |
| Role layout and lint conformance | `ansible:role-checker` |
| Secrets in git history | nothing in this marketplace covers it; say so |

The question here is about design: what happens to the *next* caller. A repository with no
remote, or one hosted anywhere, works the same way.

## References

Load the one that matches each interface, and only when you reach it.

| File | Read when the interface is… |
|---|---|
| [crypto-apis.md](references/crypto-apis.md) | anything that signs, hashes, encrypts or draws random bytes |
| [auth-sessions.md](references/auth-sessions.md) | sign-in, session or token handling, access checks, second factors |
| [config-schemas.md](references/config-schemas.md) | a settings file or struct, a flag, an env var, a constructor argument |
| [lang-go.md](references/lang-go.md) | a Go package |
| [lang-python.md](references/lang-python.md) | a Python module |
| [lang-typescript.md](references/lang-typescript.md) | a JavaScript or TypeScript module |
| [lang-bash.md](references/lang-bash.md) | a shell script, or a CI `script:` block |
| [library-lessons.md](references/library-lessons.md) | a thin layer over a native or widely used library |
| [ansible-yaml.md](references/ansible-yaml.md) | an Ansible role, or any YAML a role reads |
| [terraform.md](references/terraform.md) | a Terraform module |
| [ci-github-actions.md](references/ci-github-actions.md) | a GitHub Actions workflow, reusable workflow or action — first CI file |
| [ci-gitlab.md](references/ci-gitlab.md) | a GitLab CI pipeline or include — second CI file |

For any workflow review, settle the five lead patterns of the GitHub Actions reference before
the rest.

## Six ways an interface cuts

Tag every finding with one of these.

| Category | The edge | Look at |
|---|---|---|
| Algorithm and mode selection | the caller or the input picks the primitive | `alg`, `mode`, `cipher`, `hash` parameters and string enums; JWT `alg: none`, an RSA public key accepted as an HMAC secret |
| Dangerous defaults | the default, or a zero/empty value, switches a control off | what each degenerate value does |
| Primitive instead of semantic types | keys, nonces, tokens, MACs share `[]byte`/`str`; neighbours swap silently | adjacent same-typed parameters; `==` on MACs |
| Configuration cliffs | one wrong value fails catastrophically | mistyped booleans, `-1` timeouts, an auth-exempt path of `/`, risky combinations, env overrides |
| Silent failures | the failure looks like success | dropped errors, bool verdicts, log-and-continue, fallback on parse error, `\|\| true`, `ignore_errors: true`, "no key, skip verify" |
| Stringly-typed security | roles, scopes, URLs, commands as free text or concatenation | no enum or `choices:`, templated shell |

## Method

### 1. Map the surface

List the security-relevant interfaces in scope (or the ones the user named), then every choice
a caller makes through them:

- parameters for auth, authorisation, crypto, sessions, validation, TLS, file and network
  access; anything named algorithm, timeout, mode, path, URL or permission;
- config files and structs, environment variables, CLI flags;
- role variables (`defaults/`, `meta/argument_specs.yml`, every variable tasks and templates
  read), Terraform `variable` blocks and where each lands;
- workflow triggers, `uses:` refs, `permissions:`, action and reusable-workflow `inputs`,
  GitLab `include:` inputs and `rules:`.

Use `git ls-files` and `grep -rn` to find them; read each definition and the code it feeds.

### 2. Feed it bad values

For every choice point, work out what each of these does, from the code, without running it:

| Probe | Typical surprise |
|---|---|
| `0` | unlimited, never expires, check skipped |
| `""` | empty key or password accepted, matches an empty stored value |
| `nil` / `null` / unset | "skip", or a permissive fallback |
| `[]` | allowlist empty means allow all |
| `-1` | infinite, or wraps |
| `"false"`, `"no"`, `flase` | truthy string, YAML coercion, ignored typo |
| right type, wrong meaning | swapped arguments, `0.0.0.0/0`, `/` as a path, a public key as a secret |
| plainly invalid | accepted silently instead of rejected |

For each parameter answer three questions: what do the degenerate values mean, is the default
the safe choice, and can any single value turn security off wholesale?

### 3. Picture three callers

- **The adversary** controls a config value, an input or a PR. Can they disable a check,
  downgrade an algorithm, inject into a command?
- **The copier** pastes the first example in the README or the test file. Is that example
  safe? Is the shortest possible call safe?
- **The misreader** half-understands the contract. Can two arguments trade places and still
  compile? Is a failure visible, or does it look like success?

### 4. Prove it or drop it

- Write the smallest misuse: caller code, a vars file, module inputs, a workflow snippet.
- Trace what happens, citing `path:line` at each hop, until the security outcome is concrete.
- Check whether the docs warn about it. A warning lowers severity; it never cancels a finding.
- If you cannot show the misuse leading somewhere bad, drop the candidate.

### 5. Grade

| Severity | When |
|---|---|
| CRITICAL | the default or the most obvious call is already unsafe (TLS checks off by default, a blank password accepted) |
| HIGH | one likely slip breaks security (an algorithm parameter that takes `none`) |
| MEDIUM | a rare but believable bad value (a negative timeout meaning no expiry) |
| LOW | only a contrived mix of arguments causes harm |

Validation protects every caller; a safe default protects only the callers who set nothing.
Prefer fixes that do both.

## Large surfaces

When the scope holds more interfaces than you can probe properly in one pass (several packages,
roles, modules or workflows), give each its own `sharp-edges:sharp-edges-analyzer`, five at
most running at once. Hand each one the repository path and exactly one interface with its
files: a package; a role with `defaults/`, `meta/argument_specs.yml` and tasks; a module's
`variables.tf` and the resources using it; a workflow or include with its inputs and jobs. Use
that full agent name, never a general-purpose agent. Merge their findings, re-check any that
lack a traced outcome, and keep their Reviewed/Not reviewed lines for the summary.

## Pushback you will hear

| Argument | Answer |
|---|---|
| "The docs cover it" | make the default safe, or remove the unsafe option |
| "Experts need the knobs" | a safe high-level call, with the primitives out of the easy path |
| "Nobody would do that" | design for a hurried, confused caller; someone will |
| "It's only a setting" | validate it and refuse risky combinations |
| "We can't break compatibility" | a loud deprecation now and a forced migration on a date |

## Before you answer

- [ ] every choice point in scope was probed with the values in step 2;
- [ ] each default checked, and each override path checked for validation;
- [ ] algorithm and mode selection checked wherever crypto is configurable;
- [ ] adjacent same-typed parameters checked for silent swaps;
- [ ] all three callers considered;
- [ ] error paths checked for skipping a security step;
- [ ] every finding has a written misuse and a traced outcome.

## Report

Reply in chat; write no files in the repository. Order findings by severity.

```text
### CRITICAL · Dangerous defaults · Client skips certificate checks unless told otherwise

Interface: client/options.go:23
Misuse:
    c := client.New(client.Options{BaseURL: url})   // VerifyTLS left at its zero value
Result: VerifyTLS is false by default → options.go:31 sets InsecureSkipVerify →
    every request from sync.go:57 accepts any certificate.
Fix: invert the field to SkipTLSVerify so the zero value is the safe one, and reject
    it unless a test build tag is set.
```

Every finding gets a `path:line`. When the problem is something absent (no `permissions:`
block, no `validation`), cite the line where it belongs: the top of the file, the `jobs:` key,
the job or the `variable` block.

Fixes are design changes: remove the option, validate it, flip the default, change the type,
split the function. "Document it" is not a fix.

Close with a coverage summary:

```text
Reviewed: <interface> — <choice points probed>
Not reviewed: <interface or file> — <reason: out of scope, generated, unreadable, too large>
```

An empty findings list is a valid result only next to that summary.
