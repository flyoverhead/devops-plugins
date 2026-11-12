# Where promises live, and where they are kept

## Documents that count

A document counts when it states what the software does or refuses to do. Typical carriers:

- README sections headed *Guarantees*, *Security*, *Limits*, *Behaviour*, or a plain list of
  "X always / never Y";
- design notes, ADRs, RFC-style docs in `docs/`;
- OpenAPI / Swagger: `required`, `maxLength`, `enum`, `security` per operation, response codes;
- doc comments that state semantics ("returns ErrExpired after the TTL", "safe for
  concurrent use"), not ones that restate a name;
- Ansible role README and `meta/argument_specs.yml`;
- Terraform `variable` `description` text and module README;
- CI: GitHub Actions `inputs:` / `workflow_call` descriptions, GitLab CI component
  `spec: inputs:` descriptions, and the README of a reusable workflow or component;
- `--help` / usage text of a CLI or script.

Not counted: CHANGELOG entries, CONTRIBUTING, build or release instructions, TODO lists,
issue templates.

## Per stack

Each table row: where the requirement is written, where enforcement normally sits, where it
hides when it is not there, and what has to be searched before `absent` is believable.

### Go and Python services

| | |
|---|---|
| Written in | README, OpenAPI, doc comments, design notes |
| Enforced by | middleware, request validation, DB constraints, route registration |
| Hides in | wrappers around handlers, route groups, migrations (uniqueness, NOT NULL), decorators, dependency-injected checkers |
| Absent is credible when | every route that reaches the behaviour was enumerated from the route table, and each one was walked |

The unit of checking is the route table, not the handler named in the doc. A rule about
"every request" is checked on every registered route. Consistency across operations is a
question about transactions, not about each handler alone.

### CLIs and Bash

| | |
|---|---|
| Written in | `--help`, usage functions, README usage section |
| Enforced by | flag parsing and validation, `set -euo pipefail`, early exit on bad input |
| Hides in | sourced libraries, wrapper scripts, the CI job that calls the script |
| Absent is credible when | every entry point was checked: flags, environment variables, stdin, config files |

### Ansible roles

| | |
|---|---|
| Written in | role README, `meta/argument_specs.yml` |
| Enforced by | `required`, `choices`, `type` in argument_specs; `assert`, `fail`, `when` |
| Hides in | `defaults/` versus `vars/` precedence, `include_tasks` / `import_tasks`, dependent roles in `meta/main.yml`, the playbook |
| Absent is credible when | argument_specs, every included task file, `meta` dependencies and the documented playbook were read |

- README says "required" but argument_specs has no `required: true` and `defaults/` sets
  `""` → `absent` or `contradicted`.
- A secrets guarantee needs `no_log: true` on every task that touches the value, including
  loops and any `register` later printed with `debug`.
- "Safe to re-run" needs `changed_when`, `creates`/`removes` or a module that is idempotent
  by nature; a bare `command` or `shell` contradicts it.

### Terraform modules

| | |
|---|---|
| Written in | module README, `variable` `description` |
| Enforced by | `validation` blocks, `precondition` / `postcondition`, type constraints |
| Hides in | `locals`, submodules, provider defaults, a `validate.tf` file |
| Absent is credible when | variables, validations, every resource that consumes the input and the submodules were read |

- "Must be a private CIDR" with no `validation` on the variable → `absent`.
- "Never opens 0.0.0.0/0" where one rule is built from an unvalidated input → `partial`.

### CI pipelines

GitHub Actions workflows and reusable workflows first, GitLab CI components second.

| | |
|---|---|
| Written in | README, input descriptions |
| Enforced by | `if:` / `rules:`, input `type: choice` / `options` / `regex`, guards in `script` / `run` |
| Hides in | reusable workflows and `uses:`, `include:` templates, `extends`, repository or project settings that are not in the repo |
| Absent is credible when | every job was checked, not only the one named in the doc, and the unseen settings are named |

"Runs only on protected branches" is checked against every job. Branch protection, required
reviewers and environment rules live outside the repository: say that part was not seen.
