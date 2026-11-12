---
name: molecule-scaffolder
description: Generates a molecule test suite for an existing Ansible role — a `default` scenario on systemd-capable containers (Debian 12 and Ubuntu 24.04 by default, Debian 13 and Ubuntu 22.04 on request) on Docker or Podman, converge/idempotence/verify with ansible.builtin.assert, a GitHub Actions workflow, and a check-mode and idempotence audit of the role's tasks. Use when asked to add molecule tests, scaffold a test suite, test a role in containers or CI, or prove a role is idempotent. Not for creating a role — use ansible:role-creator; not for checking or restructuring one — use ansible:role-checker.
argument-hint: "[role-path]"
effort: high
paths: ["roles/**", "ansible/roles/**", "**/molecule/**"]
allowed-tools: Bash(molecule syntax:*) Bash(molecule list:*) Bash(molecule drivers:*) Bash(molecule test:*) Bash(molecule destroy:*) Bash(CONTAINER_ENGINE=podman molecule syntax:*) Bash(CONTAINER_ENGINE=podman molecule test:*) Bash(docker info:*) Bash(podman info:*) Bash(ansible-lint:*) Bash(yamllint:*) Bash(actionlint:*) Bash(pre-commit run:*) Bash(git status:*) Bash(git diff:*) Bash(ls:*) Bash(grep:*) Read Write Edit Glob Grep
---

# Molecule scaffolder

Target role: $ARGUMENTS (if empty, the role the user named, or the current directory when
it has `tasks/main.yml`).

Paths in the request (`roles/<role>`) are relative to the current working directory — the
user's repository — never to this skill's own directory.

The role rules are in [RULES.md](../role-creator/references/RULES.md), shared with
`ansible:role-creator` and `ansible:role-checker`. The suite layout, platform images,
driver switch, verify patterns and pitfalls are in
[references/MOLECULE.md](references/MOLECULE.md). Copy files from
[references/templates/](references/templates/) rather than retyping them.

## Checklist

Copy and track:

- [ ] 1. Read the role: `ls -R <role>`, `grep -n -A8 platforms <role>/meta/main.yml`, every file in `tasks/`, `handlers/`, `defaults/`, `vars/`, `templates/`; record the install method, observable end state and platforms.
- [ ] 2. Layout gate: apply [Stage-file layout](#stage-file-layout). If it matches, stop and point to `/ansible:role-checker`.
- [ ] 3. Choose platforms from `meta/main.yml` ([table](references/MOLECULE.md#platforms-and-images)); list any platform the images do not cover.
- [ ] 4. Write `molecule/default/`: `molecule.yml`, `Dockerfile.j2`, `prepare.yml`, `converge.yml`, `verify.yml`, and `requirements.yml` when the role uses a collection outside `ansible.builtin`.
- [ ] 5. Audit the role for check mode and idempotence ([Audit](#audit-the-role)); fix read-only probes, report the rest.
- [ ] 6. Write or extend `.github/workflows/molecule.yml`.
- [ ] 7. Validate (see [Validate](#validate)); fix and re-run until each check exits 0.
- [ ] 8. Report and stop (see [Report](#report)). Commit only when asked.

## Stage-file layout

This skill assumes the recommended layout from RULES.md: `tasks/install.yml`, `configure.yml`,
`service.yml`, no detect facts. Stop without writing anything when either holds:

- `tasks/detect.yml` or `tasks/update.yml` exists;
- `grep -rnE '^\s+(\w+_(installed|update):|register:\s*\w+_(installed|update)\s*$)' <role>/tasks`
  finds a match.

Say which file or line matched and tell the user to run `/ansible:role-checker <role>`
first, which restructures the role; then re-run this skill. A role that only lacks
`meta/argument_specs.yml` or has a `config.yml` is not blocked: scaffold, and list the gap
in the report.

## What the suite looks like

```
<role>/molecule/default/
├── molecule.yml      driver ${CONTAINER_ENGINE:-docker}, platforms, test_sequence
├── Dockerfile.j2     pinned base image + systemd + python3
├── prepare.yml       wait for systemd, refresh apt, install test-only dependencies
├── converge.yml      applies the role by directory name, with representative values
├── verify.yml        ansible.builtin.assert on the observed end state
└── requirements.yml  only when the role needs collections
.github/workflows/molecule.yml
```

- `test_sequence` is `dependency, create, prepare, converge, idempotence, verify, destroy`.
  `prepare` runs once, so the idempotence step re-runs converge alone.
- One scenario serves Docker and Podman: `CONTAINER_ENGINE=podman molecule test` switches
  the driver. Platform entries use only keys both drivers accept; MOLECULE.md explains
  why `cgroupns_mode`, `tmpfs` and `${MOLECULE_DRIVER}` are not used.
- Never write `create.yml` or `destroy.yml`; the driver supplies them.
- Files under `<role>/molecule/` are linted as part of the role, so every registered
  variable is `<role>_molecule_*` (`var-naming[no-role-prefix]`). Keep the
  `# noqa: command-instead-of-module` on the `systemctl is-system-running` probe; no module
  reports that state.
- `converge.yml` sets values that exercise the configure path, not just the defaults.
  Per-distro values go on `ansible_facts['distribution_release']`.
- `verify.yml` asserts what a user would observe — package or binary version, service
  running and enabled, listening port, rendered config content, created user — never the
  role's own registered results. Patterns in
  [MOLECULE.md](references/MOLECULE.md#verifyyml).

## Audit the role

`molecule test` proves idempotence; these greps find the usual causes before the first
run. Run each from the role directory:

```bash
grep -n -B2 -A6 'ansible.builtin.\(command\|shell\)' tasks/*.yml   # read-only probe without check_mode: false?
grep -rn "state: touch" tasks/                                  # needs *_time: preserve
grep -rn "dest: /tmp/" tasks/                                   # download path without the version
grep -rnE "\{\{ *ansible_[a-z]" tasks/ templates/               # injected facts; use ansible_facts[...]
grep -rn "become_user:" tasks/                                  # needs acl in the image
grep -rn "default('')" tasks/                                   # check-mode guard that feeds an empty value on
```

Fix without asking: add `check_mode: false` (and `changed_when: false` if missing) to a
`command`/`shell` task that only reads state (`--version`, `systemctl is-active`,
`apt-cache policy`) and whose result a later task uses. Under `--check` such a task is
skipped, and the next `.stdout` read aborts the run. Everything else on the list changes
behaviour: report it with `path:line` and a proposed fix, and ask. Details and fixes are in
[MOLECULE.md](references/MOLECULE.md#pitfalls).

## Validate

From the role directory:

1. `molecule syntax` — exits 0. When the podman driver is installed
   (`molecule drivers` lists it), also `CONTAINER_ENGINE=podman molecule syntax`.
2. Lint the new files: `pre-commit run --files <molecule/ files> .github/workflows/molecule.yml`
   when the repo has `.pre-commit-config.yaml`, else `ansible-lint` and `yamllint` on
   `molecule/` and the role, and `actionlint .github/workflows/molecule.yml` when it is
   installed.
3. `molecule test` when `docker info` (or `podman info` with `CONTAINER_ENGINE=podman`)
   succeeds. Read the idempotence step: every host must show `changed=0`. On failure the
   log names the task; fix the role or the suite, then re-run. A failed run leaves
   containers behind only if it was interrupted: `molecule destroy` cleans up.

Never run `ansible-playbook` against real hosts here; molecule drives local containers
only. If no container engine is available, say that `molecule test` did not run and give
the command.

## Report

- The files written, and every role file changed by the audit with `path:line`.
- Platforms covered, and platforms in `meta/main.yml` that are not.
- Each check with its command and exit code; for `molecule test`, the converge and
  idempotence recap lines (`changed=0`).
- Not verified: anything skipped (no engine, Podman path, platforms without an image).
- Numbered questions for the audit findings that need a yes.

Then stop. Show `git status`, and commit only when the user asks, with `git commit -s`.

## Comment discipline

Generated files carry no boilerplate comments; the rationale lives in MOLECULE.md. Add a
comment only where it is specific to this role and the next reader would otherwise undo
it — why a value is pinned per release, why a test-only package is installed in
`prepare.yml`, a machine-read directive such as `# noqa: <rule>`. One line each.

## References

- [references/MOLECULE.md](references/MOLECULE.md) — platforms and images, the driver
  switch, each generated file, the GitHub workflow, an optional update scenario, pitfalls
  and check-mode patterns.
- [references/templates/](references/templates/) — `molecule.yml`, `Dockerfile.j2`,
  `prepare.yml`, `converge.yml`, `verify.yml`, `requirements.yml`, `github-molecule.yml`.
- [../role-creator/references/RULES.md](../role-creator/references/RULES.md) — the rules
  the audited role follows.

## Limits

- `git diff`, `git show`, `git log`: never `--output`, `--ext-diff` or `--textconv`; they write
  files or run external programs. Every `git diff`, `git show` and patch-showing `git log` carries
  `--no-ext-diff --no-textconv`.
