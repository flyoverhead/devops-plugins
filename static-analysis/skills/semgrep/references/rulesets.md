# Rulesets and language detection

## Contents

- Detecting languages
- Registry packs per language
- Opt-in registry packs
- Third-party rule repositories
- Notes on ids

## Detecting languages

Glob with `**/` so nested manifests and sub-projects count. Report vendored trees
(`vendor/`, `node_modules/`, `third_party/`) separately if they dominate the count.

| Language key | Globs |
|---|---|
| `go` | `**/*.go` |
| `python` | `**/*.py`, `**/*.pyi` |
| `javascript` | `**/*.js`, `**/*.jsx`, `**/*.mjs`, `**/*.cjs` |
| `typescript` | `**/*.ts`, `**/*.tsx` |
| `bash` | `**/*.sh`, `**/*.bash` |
| `terraform` | `**/*.tf`, `**/*.tfvars`, `**/*.hcl` |
| `dockerfile` | `**/Dockerfile`, `**/*.dockerfile` |
| `yaml` | `**/*.yml`, `**/*.yaml` |
| `ruby` | `**/*.rb`, `**/*.erb` |
| `java` | `**/*.java` |
| `kotlin` | `**/*.kt`, `**/*.kts` |
| `php` | `**/*.php` |
| `c` / `cpp` | `**/*.c`, `**/*.h` / `**/*.cpp`, `**/*.cc`, `**/*.cxx`, `**/*.hpp`, `**/*.hh` |
| `csharp` | `**/*.cs` |
| `rust` | `**/*.rs` |
| `scala`, `swift`, `elixir`, `apex`, `solidity` | `*.scala`; `*.swift`; `*.ex`, `*.exs`; `*.cls`, `*.trigger`; `*.sol` |

The runner scopes each language ruleset with the same globs (`--include`). `.mts`, `.cts`,
`Containerfile` and `Dockerfile.prod` are not in the include table, so files with those names
are only seen by the cross-language rulesets; say so in the plan when they exist.

**YAML** is split by content. Read a sample of files, infrastructure-looking paths first:

- `github-actions` for workflow files (the `.github/workflows/` directory);
- `apiVersion:` and `kind:` at top level → `kubernetes`;
- CloudFormation when a template declares its format version or lists resources typed `AWS::…`
  (no registry pack; `p/default` covers some rules);
- anything else → generic YAML. Whenever any YAML exists, keep the `yaml` key as well.

**JSON** gets a category only when it holds CloudFormation markers or an IAM policy shape
(`Statement` entries with `Effect`). Build and tool config (`package.json`, `tsconfig*.json`,
lockfiles) gets none.

**Framework hints** come from manifests found with `**/package.json`, `**/pyproject.toml`,
`**/requirements*.txt`, `**/Gemfile`, `**/composer.json`, `**/go.mod`, `**/Cargo.toml`,
`**/pom.xml`. Grep them for the framework name.

## Registry packs per language

Pre-select the baseline and the pack of every detected language.

| Detected | Pack(s) |
|---|---|
| baseline (always) | `p/default`, `p/secrets` |
| go | `p/golang` |
| python | `p/python`; framework: `p/django`, `p/flask`, `p/fastapi` |
| javascript | `p/javascript`, `p/nodejs`; framework: `p/react`, `p/nextjs`, `p/expressjs` |
| typescript | `p/typescript`; same framework packs as javascript |
| terraform | `p/terraform` |
| dockerfile | `p/dockerfile`; compose files: `p/docker-compose` |
| github-actions | `p/github-actions` |
| kubernetes | `p/kubernetes` |
| java | `p/java` |
| kotlin | `p/kotlin` |
| ruby | `p/ruby` |
| php | `p/php`; Laravel: `p/php-laravel` |
| c, cpp | `p/c` |
| csharp | `p/csharp` |
| rust | `p/rust` |
| scala, swift, elixir, apex | `p/scala`, `p/swift`, `p/elixir`, `p/apex` |
| bash, generic yaml, solidity | no dedicated registry pack; `p/default` and the third-party repos below |

Spring, Rails, Angular and Symfony have no registry pack of their own; the language pack
covers them.

## Opt-in registry packs

Shown unticked. Each broadens coverage and adds noise.

| Pack | What it adds |
|---|---|
| `p/security-audit` | audit-grade rules, many low-confidence |
| `p/owasp-top-ten` | rules tagged by OWASP category |
| `p/cwe-top-25` | rules tagged by CWE Top 25 |
| `p/sql-injection`, `p/command-injection`, `p/xss`, `p/jwt` | one vulnerability class each |
| `p/insecure-transport` | plain HTTP, disabled TLS checks |
| `p/gitleaks` | secret patterns modelled on the gitleaks rule set |
| `p/ci`, `p/r2c-ci` | CI-friendly low-noise sets |

## Third-party rule repositories

Opt-in only, offered when a detected language matches, cloned shallow and unpinned
(`git clone --depth 1`) into `repos/`. Always cloned, never passed as a URL config: some of
these repos hold YAML that is not a rule file and breaks URL loading. The runner prunes files
without a top-level `rules:` key and join-mode rules before scanning. State each licence in
the plan.

| Repository | Languages | Licence note |
|---|---|---|
| `https://github.com/trailofbits/semgrep-rules` | Python, Go, Ruby, JS/TS, Terraform | AGPL-3.0 |
| `https://github.com/dgryski/semgrep-go` | Go | check repo |
| `https://github.com/0xdea/semgrep-rules` | C, C++ | check repo |
| `https://github.com/Decurity/semgrep-smart-contracts` | Solidity, Cairo, Rust | check repo |
| `https://github.com/mindedsecurity/semgrep-rules-android-security` | Java, Kotlin (Android) | check repo |
| `https://github.com/elttam/semgrep-rules` | several | check repo |
| `https://github.com/kondukto-io/semgrep-rules` | several | check repo |
| `https://github.com/federicodotta/semgrep-rules` | Java, Kotlin | check repo |
| `https://github.com/hashicorp-forge/semgrep-rules` | Go, Terraform | check repo |
| `https://github.com/akabe1/akabe1-semgrep-rules` | several | check repo |
| `https://github.com/atlassian-labs/atlassian-sast-ruleset` | several | check repo |
| `https://github.com/apiiro/malicious-code-ruleset` | JS, Python (malicious code) | check repo |

"check repo" means: read the repo's licence file after cloning and put it in the report.

## Notes on ids

- Registry ids above were checked against `semgrep.dev/c/p/<id>` on 2026-11-11. A pack that
  disappears shows as a failed scan in `scans.json`; report it, do not swap in another.
- Do not run `semgrep --validate` to test a pack: it downloads a lint pack before approval.
