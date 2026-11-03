# Molecule suite reference

Details for `ansible:molecule-scaffolder`. The files themselves are in
[templates/](templates/); this page explains them and the traps a suite runs into.
Substitute `<role>`, `<pkg>`, `<service>`, `<port>`, `<config-path>` throughout.

## Contents

- [Platforms and images](#platforms-and-images)
- [Docker or Podman](#docker-or-podman)
- [molecule.yml](#moleculeyml)
- [prepare.yml](#prepareyml)
- [converge.yml](#convergeyml)
- [verify.yml](#verifyyml)
- [requirements.yml](#requirementsyml)
- [GitHub Actions workflow](#github-actions-workflow)
- [Check mode](#check-mode)
- [Optional update scenario](#optional-update-scenario)
- [Pitfalls](#pitfalls)

## Platforms and images

Each platform is built from a pinned official image by `Dockerfile.j2`, which adds
`systemd`, `systemd-sysv`, `python3`, `python3-apt`, `sudo` and `ca-certificates`, and
starts `/sbin/init`. Building from the distribution's own image keeps the suite free of
third-party images and lets the tag be pinned exactly; the layer cache makes rebuilds
quick.

| `meta/main.yml` platform | Platform name | Image (verified 2026-11-03) |
|---|---|---|
| Debian `bookworm` | `debian12` | `debian:12.15` |
| Debian `trixie` | `debian13` | `debian:13.7` |
| Ubuntu `jammy` | `ubuntu2204` | `ubuntu:jammy-20261020` |
| Ubuntu `noble` | `ubuntu2404` | `ubuntu:noble-20260917` |

- The template has `debian12` and `ubuntu2404`. Add `debian13` or `ubuntu2204` (a copy of
  an entry with the image from the table) when the role lists that release; drop an entry the role does not
  support. The scenario follows `meta/main.yml`; when the two disagree, one of them is
  wrong — say so.
- RHEL family and Windows are not covered by these images. List them in the report as not
  tested.
- To bump a tag, check it exists first:
  `docker manifest inspect debian:<tag> >/dev/null && echo ok`. Debian point tags
  (`12.15`) and Ubuntu date tags (`noble-YYYYMMDD`) do not move; `12`, `bookworm` and
  `24.04` do.
- A role that needs extra OS packages only for testing (a daemon an exporter scrapes,
  `acl` for `become_user`) installs them in `prepare.yml`, not the Dockerfile, so the
  image stays the same for every role.

## Docker or Podman

`driver.name` is `${CONTAINER_ENGINE:-docker}`:

```bash
molecule test                              # Docker
CONTAINER_ENGINE=podman molecule test      # Podman; needs molecule-plugins[podman]
```

Constraints behind the template, each checked against molecule 26.10 and
molecule-plugins 26.11:

- **Not `${MOLECULE_DRIVER:-docker}`.** Molecule resolves the driver before it expands
  variables that start with `MOLECULE_`, so any `MOLECULE_*` variable in `driver.name`
  fails with `Failed to find driver $MOLECULE_DRIVER:-docker`. A variable outside that
  prefix expands normally. `molecule test --driver-name podman` also works, but logs a
  warning that the scenario defines another driver.
- **No `cgroupns_mode`.** The podman driver's schema rejects it
  (`Additional properties are not allowed ('cgroupns_mode' was unexpected)`).
- **No `tmpfs`.** The docker schema wants a list and the podman schema a mapping, so no
  value passes both.
- **`privileged: true` and `command: ""`** pass both schemas. `command: ""` keeps the
  image's `/sbin/init` instead of the driver's default sleep loop. Under Docker,
  `privileged` with the default private cgroup namespace gives systemd a writable
  `cgroup2` mount; under Podman, `/sbin/init` as the command turns on its systemd mode.
- `role_name_check: 1` turns molecule's galaxy role-name check into a warning, so roles
  whose `meta/main.yml` has no `namespace` still run.
- **cgroup v2.** Docker without `cgroupns: host` and rootless Podman need a cgroup v2
  host; rootless Podman also needs cgroup v2 delegation to the user.

Status: the Docker path is verified end to end (`molecule test`, idempotence
`changed=0`). The Podman path passes `molecule syntax` with the podman driver; a full
Podman run has not been verified.

## molecule.yml

Template: [templates/molecule.yml](templates/molecule.yml). Beyond the platforms:

- `provisioner.config_options.defaults.inject_facts_as_vars: false` makes a role that reads
  `ansible_os_family` instead of `ansible_facts['os_family']` fail in the suite, as it
  would on a controller configured the same way.
- `ANSIBLE_ROLES_PATH: ${MOLECULE_PROJECT_DIRECTORY}/..` lets `converge.yml` find the role
  by its directory name.
- `test_sequence` lists `prepare` explicitly; an explicit sequence runs only the steps it
  names. `prepare` is not repeated by the idempotence step.
- `dependency: galaxy` installs `requirements.yml` from the scenario directory when it
  exists and skips the step when it does not.

## prepare.yml

Template: [templates/prepare.yml](templates/prepare.yml). It waits until
`systemctl is-system-running` reports `running` or `degraded` (a container may report
`degraded` for units it cannot start), then refreshes the apt index: the image ships
without one, and a role whose `apt` task uses `cache_valid_time` would otherwise skip the
refresh and find no package.

Its registered variable is `<role>_molecule_systemd_state`; every variable registered in the
suite carries the role prefix (`var-naming[no-role-prefix]`). Keep the
`# noqa: command-instead-of-module`: no module reports `is-system-running`.

Add role-specific setup here, never in `converge.yml`: anything converge repeated would be
part of the idempotence check. Examples: the daemon an exporter scrapes, a database the
role connects to, an older version for an update scenario.

## converge.yml

Template: [templates/converge.yml](templates/converge.yml). It applies the role by the
project directory's name, so it needs no edit to find the role. Add `vars:` to the
`include_role` task with values that exercise the configure path — a non-default port, an
extra config option, a second item in a list — so `verify.yml` can prove they reached the
host. Values that differ per release go on `ansible_facts['distribution_release']`:

```yaml
      vars:
        <role>_version: "{{ '4.6' if ansible_facts['distribution_release'] == 'trixie' else '4.3' }}"
```

## verify.yml

Template: [templates/verify.yml](templates/verify.yml). Assert the end state independently
of the role's own tasks. Cover what applies:

| Install method | Assert |
|---|---|
| package | `'<pkg>' in ansible_facts['packages']` (from `ansible.builtin.package_facts`), and the version when the role pins one |
| binary | `<binary> --version` output contains the wanted version (`command`, `changed_when: false`, `register`, then `assert`) |
| container | the container is running (`community.docker.docker_container_info` or `containers.podman.podman_container_info`) |
| any | service running and enabled, listening port (`ansible.builtin.wait_for`), user and group (`ansible.builtin.getent`), rendered config contains the converge values (`ansible.builtin.slurp` + `b64decode`), an HTTP endpoint answers (`ansible.builtin.uri`) |

- `service_facts` keys are full unit names: `ansible_facts['services']['chrony.service']`.
  Guard with `| default('')` so a missing unit fails the assertion with its `fail_msg`
  instead of an undefined-variable error.
- Give every `assert` a `fail_msg` that shows the actual value.
- Prometheus samples may carry labels: `squid_up{host="localhost"} 1`. Match the line with
  an anchored regex, which also accepts `1.0`:
  `content is search('(?m)^squid_up(\{[^}]*\})?\s+1(\.0+)?$')`.
- An exporter with nothing to scrape still serves `/metrics` and reports `<x>_up 0`.
  Install the target in `prepare.yml` and assert `_up 1`; asserting only the port proves
  little.
- A Debian package version may have no patch component (`4.3-2+deb12u3`). Match a pin with
  `version is match(pin | regex_escape ~ '[.-]')`, which accepts `4.3-2` and `4.3.1-1`
  and rejects `4.30-1`.

## requirements.yml

Write [templates/requirements.yml](templates/requirements.yml) when the role, `prepare.yml`
or `verify.yml` uses a module, filter or lookup from a collection other than
`ansible.builtin` (`grep -rhoE '\b(community|containers|ansible\.posix)\.[a-z_]+' <role>`).
List each collection with a minimum version. The docker and podman drivers install their
own collections (`community.docker`, `containers.podman`) at start-up.

## GitHub Actions workflow

Template: [templates/github-molecule.yml](templates/github-molecule.yml), written to
`.github/workflows/molecule.yml`. It runs `molecule test` on `ubuntu-latest` after
`pip install molecule 'molecule-plugins[docker]' ansible-core`.

- Several roles share one workflow: add each to `matrix.role`. If the workflow exists,
  extend the matrix instead of writing a second file.
- A repository that is a single role (`tasks/` at the root) drops the matrix and
  `working-directory`.
- Action majors were current on 2026-11-03 (`actions/checkout@v7`,
  `actions/setup-python@v7`). Check with
  `gh api repos/actions/checkout/releases/latest --jq .tag_name` before changing them, and
  run `actionlint` on the result.
- The workflow is the default for GitHub. In a repository hosted elsewhere, write the same
  three steps (Python, `pip install`, `molecule test` in the role directory) in that CI's
  format, or skip the workflow and say so.

## Check mode

A role should survive `--check`, because that is how it is run before a real change. The
suite does not include a `check` step, but the scaffolder audits for the pattern behind
most check-mode failures:

```yaml
- name: Read chrony version
  ansible.builtin.command: chronyd --version
  register: chrony_version_output
  changed_when: false

- name: Show chrony version
  ansible.builtin.debug:
    msg: "{{ chrony_version_output.stdout }}"
```

Under `--check` the `command` task is skipped, so `.stdout` is undefined and the next task
aborts. The fix for a read-only command is `check_mode: false`, so it runs in both modes:

```yaml
- name: Read chrony version
  ansible.builtin.command: chronyd --version
  register: chrony_version_output
  changed_when: false
  check_mode: false
```

Apply it only to commands that change nothing. A command that changes state is guarded so
its consumers tolerate `ansible_check_mode`, which is a behaviour change to ask about.

To exercise check mode against a converged host, run `molecule converge` and then
`molecule check`. `molecule check` fails only when the playbook fails; it does not assert
`changed=0`, since some modules report changes in check mode.

## Optional update scenario

Worth adding when updating is a real code path — typically binary installs, which compare
the installed `--version` with `<role>_version` and replace the binary when they differ.
Create `molecule/update/` with the same `molecule.yml` and `Dockerfile.j2`, then:

- `prepare.yml` applies the role with the older version:
  `include_role` with `vars: {<role>_version: "<from-version>"}`;
- `converge.yml` applies it with the default (newer) version;
- `verify.yml` asserts the newer version is installed and the older one is not.

The older version must go in `prepare`, not in a first converge play: with an "update when
different" check, a two-play converge downgrades and upgrades again on every run and can
never pass idempotence. `prepare` runs once. Only add the scenario when both versions are
still downloadable, and run it with `molecule test -s update`.

## Pitfalls

Each of these passes `converge` and fails `idempotence` or `verify`, or fails only on
some hosts:

- **`state: touch`** reports `changed` on every run. Add `modification_time: preserve` and
  `access_time: preserve`.
- **A download path without the version** (`dest: /tmp/<tool>.tar.gz`). `get_url` skips the
  download when the file exists, so the first version fetched stays forever and an upgrade
  reports `ok`. Put the version in the path.
- **Injected facts** (`ansible_distribution`, `ansible_user_uid`) do not exist with
  `inject_facts_as_vars: false`. Use `ansible_facts['…']`.
- **`become_user`** to an unprivileged user needs `acl` on the host; the base images do not
  have it. Install `acl` in `prepare.yml` and list it in the role README as a requirement,
  or run the command with `su -s /bin/sh <user> -c '…'`.
- **`| default('')` as a check-mode guard** survives the skipped probe, then feeds an empty
  string to whatever consumes it (`version` tests fail on it). Use `check_mode: false` on
  the probe, or a sentinel the consumer accepts (`| default('0.0.0')`).
- **An available package is not an installed one.** A metapackage may pull a dependency on
  one release and not on another. When the role relies on a package it does not name,
  verify that package explicitly.
- **Upstream repositories prune old patch releases.** A role pinned to an exact patch
  breaks when the repository drops it. Check what the repository serves before pinning;
  a stale default is a finding for the role, not something to bump silently.
- **`apt` with `update_cache: true` and no `cache_valid_time`** refreshes on every run.
  Whether it reports `changed` depends on the ansible-core version; `cache_valid_time` or
  `changed_when: false` on a separate refresh task keeps idempotence stable.
- **Handlers that restart a service on every run** usually mean a template or file task is
  not idempotent: a timestamp, an unsorted dict or a `lookup('pipe', 'date')` in the
  rendered content.
