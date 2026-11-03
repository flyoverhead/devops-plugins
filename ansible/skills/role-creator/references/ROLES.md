# Role templates

Concrete file templates for each install method. Replace the role name (`nginx`,
`node_exporter`, `whoami`) and its prefix everywhere; keep the structure. Every template
passes `ansible-lint --profile production`. The rules behind them are in
`RULES.md`.

## Contents

- [tasks/main.yml](#tasksmainyml)
- [tasks/assert.yml](#tasksassertyml)
- [Package install](#package-install) — `nginx` from the distribution or a vendor apt repo
- [Binary install](#binary-install) — `node_exporter` from a GitHub release tarball
- [Container install](#container-install) — Docker or Podman, chosen by a variable
- [tasks/configure.yml](#tasksconfigureyml)
- [tasks/service.yml and handlers](#tasksserviceyml-and-handlers)
- [vars/<os_family>.yml](#varsos_familyyml)
- [meta/main.yml](#metamainyml)
- [meta/argument_specs.yml](#metaargument_specsyml)
- [Templates](#templates)
- [Windows](#windows)
- [README.md and CHANGELOG.md](#readmemd-and-changelogmd)

## tasks/main.yml

```yaml
---
- name: Include assert tasks
  ansible.builtin.include_tasks:
    file: assert.yml
    apply:
      tags:
        - always
  tags:
    - always

- name: Include OS family variables
  ansible.builtin.include_vars:
    file: "{{ lookup('ansible.builtin.first_found', nginx_vars_files) }}"
  vars:
    nginx_vars_files:
      files:
        - "{{ ansible_facts['os_family'] }}.yml"
      paths:
        - "{{ role_path }}/vars"
  tags:
    - always

- name: Include install tasks
  ansible.builtin.include_tasks:
    file: install.yml
    apply:
      tags:
        - nginx
        - nginx_install
  tags:
    - nginx
    - nginx_install

- name: Include configure tasks
  ansible.builtin.include_tasks:
    file: configure.yml
    apply:
      tags:
        - nginx
        - nginx_configure
  tags:
    - nginx
    - nginx_configure

- name: Include service tasks
  ansible.builtin.include_tasks:
    file: service.yml
    apply:
      tags:
        - nginx
        - nginx_service
  tags:
    - nginx
    - nginx_service
```

The assert include comes first, so an unsupported platform fails with its message instead
of a `first_found` lookup error. Drop the `include_vars` task when the role has no `vars/`,
and the assert include when there is no `assert.yml`.

## tasks/assert.yml

Only for checks that `argument_specs` cannot express: platform support, value relations.

```yaml
---
- name: Assert the platform is supported
  ansible.builtin.assert:
    that:
      - ansible_facts['os_family'] in ['Debian']
    fail_msg: "nginx role supports Debian and Ubuntu, not {{ ansible_facts['distribution'] }}"
    quiet: true
```

## Package install

`defaults/main.yml`:

```yaml
---
nginx_version: ""
nginx_apt_repo_enabled: false
nginx_apt_repo_url: https://nginx.org/packages/debian
nginx_apt_key_url: https://nginx.org/keys/nginx_signing.key
```

An empty `nginx_version` installs the repository candidate once and never upgrades it; a
pinned value (`1.26.2-1~bookworm`, or a prefix with `*`) installs exactly that version, so
bumping it is the update path.

`tasks/install.yml`:

```yaml
---
- name: Add nginx apt repository
  when: nginx_apt_repo_enabled
  block:
    - name: Install deb822_repository dependency
      ansible.builtin.apt:
        name: python3-debian
        state: present
        update_cache: true
        cache_valid_time: 3600

    - name: Download nginx signing key
      ansible.builtin.get_url:
        url: "{{ nginx_apt_key_url }}"
        dest: /etc/apt/keyrings/nginx.asc
        owner: root
        group: root
        mode: '0644'

    - name: Add nginx repository source
      ansible.builtin.deb822_repository:
        name: nginx
        types: deb
        uris: "{{ nginx_apt_repo_url }}"
        suites: "{{ ansible_facts['distribution_release'] }}"
        components: nginx
        signed_by: /etc/apt/keyrings/nginx.asc
        state: present

- name: Install nginx package
  ansible.builtin.apt:
    name: "{{ nginx_package_name ~ ('=' ~ nginx_version if nginx_version | length > 0 else '') }}"
    state: present
    update_cache: true
    cache_valid_time: 3600
  notify: Restart nginx
```

`nginx_package_name` comes from `vars/Debian.yml`. For a role that must also hold the
package, add `ansible.builtin.dpkg_selections` with `selection: hold` after the install.

## Binary install

The only method with an explicit detect step: the installed `--version` is compared with
the wanted one, and the download, unpack and copy run only when they differ.

`defaults/main.yml`:

```yaml
---
node_exporter_version: "1.9.1"
node_exporter_arch: "{{ {'x86_64': 'amd64', 'aarch64': 'arm64'}[ansible_facts['architecture']] | default(ansible_facts['architecture']) }}"
node_exporter_release_url: "https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}"
node_exporter_binary_path: /usr/local/bin/node_exporter
node_exporter_user: node_exporter
node_exporter_group: node_exporter
node_exporter_listen_address: "0.0.0.0:9100"
node_exporter_collectors_enabled: []
node_exporter_collectors_disabled: []
```

`tasks/install.yml`:

```yaml
---
- name: Check installed node_exporter version
  ansible.builtin.command:
    cmd: "{{ node_exporter_binary_path }} --version"
  register: node_exporter_version_check
  changed_when: false
  check_mode: false
  failed_when: false

- name: Set installed node_exporter version
  ansible.builtin.set_fact:
    node_exporter_installed_version: >-
      {{ (node_exporter_version_check.stdout ~ ' ' ~ node_exporter_version_check.stderr)
         | regex_search('[0-9]+[.][0-9]+[.][0-9]+') | default('', true) }}

- name: Create node_exporter group
  ansible.builtin.group:
    name: "{{ node_exporter_group }}"
    system: true
    state: present

- name: Create node_exporter user
  ansible.builtin.user:
    name: "{{ node_exporter_user }}"
    group: "{{ node_exporter_group }}"
    system: true
    shell: /usr/sbin/nologin
    create_home: false
    state: present

- name: Install node_exporter release
  when: node_exporter_installed_version != node_exporter_version
  block:
    - name: Download node_exporter archive
      ansible.builtin.get_url:
        url: "{{ node_exporter_release_url }}/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}.tar.gz"
        dest: "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}.tar.gz"
        checksum: "sha256:{{ node_exporter_release_url }}/sha256sums.txt"
        owner: root
        group: root
        mode: '0644'
      register: node_exporter_download
      until: node_exporter_download is succeeded
      retries: 3
      delay: 5

    - name: Unpack node_exporter archive
      when: not ansible_check_mode
      ansible.builtin.unarchive:
        src: "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}.tar.gz"
        dest: /tmp
        remote_src: true

    - name: Install node_exporter binary
      when: not ansible_check_mode
      ansible.builtin.copy:
        src: "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}/node_exporter"
        dest: "{{ node_exporter_binary_path }}"
        remote_src: true
        owner: root
        group: root
        mode: '0755'
      notify: Restart node_exporter

    - name: Remove node_exporter download files
      ansible.builtin.file:
        path: "{{ item }}"
        state: absent
      loop:
        - "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}.tar.gz"
        - "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}"
```

Adapt the version regex when the binary prints a two-part version or a `v` prefix; check
the real `--version` output of the pinned release first.

Check mode: the probe runs for real, so `--check` shows whether an install is due. On a
host that needs one, `get_url` reports `changed` without downloading, so unpack and copy
are skipped in check mode (they would fail on the missing archive). For the same reason
`tasks/service.yml` and the restart handler skip the service while the binary is not
installed yet in check mode; see [tasks/service.yml and handlers](#tasksserviceyml-and-handlers).

## Container install

`defaults/main.yml`:

```yaml
---
whoami_container_engine: docker
whoami_image: docker.io/traefik/whoami
whoami_version: "v1.11.0"
whoami_port: 8080
```

`tasks/install.yml` pulls the pinned image; `tasks/service.yml` runs the container.
Docker needs the `community.docker` collection, Podman `containers.podman`; list the one
you use in the repo's `requirements.yml`.

```yaml
---
- name: Pull whoami image with Docker
  community.docker.docker_image_pull:
    name: "{{ whoami_image }}"
    tag: "{{ whoami_version }}"
  when: whoami_container_engine == 'docker'

- name: Pull whoami image with Podman
  containers.podman.podman_image:
    name: "{{ whoami_image }}"
    tag: "{{ whoami_version }}"
    state: present
  when: whoami_container_engine == 'podman'
```

`tasks/service.yml`:

```yaml
---
- name: Run whoami container with Docker
  community.docker.docker_container:
    name: whoami
    image: "{{ whoami_image }}:{{ whoami_version }}"
    state: started
    restart_policy: unless-stopped
    published_ports:
      - "{{ whoami_port }}:80"
  when: whoami_container_engine == 'docker'

- name: Run whoami container with Podman
  containers.podman.podman_container:
    name: whoami
    image: "{{ whoami_image }}:{{ whoami_version }}"
    state: started
    restart_policy: unless-stopped
    ports:
      - "{{ whoami_port }}:80"
  when: whoami_container_engine == 'podman'
```

Podman has no daemon, so `restart_policy` does not bring the container back after a
reboot. For Podman, also generate a systemd unit (a Quadlet `.container` file in
`/etc/containers/systemd/` on Podman 4.4+) and start that instead.

`meta/argument_specs.yml` restricts the engine with `choices: [docker, podman]`. The
container module recreates the container when the image tag changes, which is the update
path. A config change notifies `Restart whoami container`, a handler with
`state: started` and `restart: true` on the same module.

## tasks/configure.yml

```yaml
---
- name: Create node_exporter textfile directory
  ansible.builtin.file:
    path: /var/lib/node_exporter/textfile
    state: directory
    owner: "{{ node_exporter_user }}"
    group: "{{ node_exporter_group }}"
    mode: '0755'

- name: Template node_exporter defaults file
  ansible.builtin.template:
    src: node_exporter.default.j2
    dest: /etc/default/node_exporter
    owner: root
    group: root
    mode: '0644'
  notify: Restart node_exporter
```

Validate a config file before it lands when the service has a checker
(`validate: nginx -t -c %s`).

## tasks/service.yml and handlers

`tasks/service.yml`:

```yaml
---
- name: Template node_exporter systemd unit
  ansible.builtin.template:
    src: node_exporter.service.j2
    dest: /etc/systemd/system/node_exporter.service
    owner: root
    group: root
    mode: '0644'
  notify: Restart node_exporter

- name: Flush node_exporter handlers
  ansible.builtin.meta: flush_handlers

- name: Start and enable node_exporter
  ansible.builtin.systemd_service:
    name: node_exporter
    state: started
    enabled: true
  when: not ansible_check_mode or (node_exporter_installed_version is defined and node_exporter_installed_version | length > 0)
```

Flushing first means a changed unit file is reloaded and the service restarted before the
start-and-enable task checks it. Package installs skip the unit template; the package
ships the unit.

`handlers/main.yml`:

```yaml
---
- name: Restart node_exporter
  ansible.builtin.systemd_service:
    name: node_exporter
    state: restarted
    daemon_reload: true
  when: not ansible_check_mode or (node_exporter_installed_version is defined and node_exporter_installed_version | length > 0)
```

The `when:` keeps `--check` usable on a fresh host: the unit file is reported as
`changed` but not written, so starting or restarting it would fail with "Could not find
the requested service". On a host with the binary installed, check mode manages the
service as usual. The `is defined` test covers a run whose tags skip `install.yml`
(`--check --tags node_exporter_configure`), where the version fact is never set.

Add `Reload <service>` with `state: reloaded` when the service supports a reload without
dropping connections.

## vars/<os_family>.yml

`vars/Debian.yml`:

```yaml
---
nginx_package_name: nginx
nginx_config_dir: /etc/nginx
```

`vars/RedHat.yml` carries the same keys with that family's values. The file name is the
exact `ansible_facts['os_family']` value (`Debian`, `RedHat`, `Windows`).

## meta/main.yml

```yaml
---
galaxy_info:
  role_name: node_exporter
  author: Jane Doe
  description: Install and configure Prometheus node_exporter from the GitHub release
  license: MIT
  min_ansible_version: '2.19'
  platforms:
    - name: Debian
      versions:
        - bookworm
        - trixie
    - name: Ubuntu
      versions:
        - noble
  galaxy_tags:
    - monitoring
    - prometheus
dependencies: []
```

`author` comes from the other roles in the repo or `git config user.name`; `license` from
the repo's licence. Galaxy tags are lowercase letters and digits only (`meta-no-tags`).

## meta/argument_specs.yml

One `options` entry per variable in `defaults/main.yml`, with the same default.

```yaml
---
argument_specs:
  main:
    short_description: Install and configure Prometheus node_exporter
    description:
      - Installs the node_exporter release binary, a system user and a systemd unit.
    options:
      node_exporter_version:
        type: str
        default: "1.9.1"
        description: Release version to install, without the leading v.
      node_exporter_arch:
        type: str
        default: "{{ {'x86_64': 'amd64', 'aarch64': 'arm64'}[ansible_facts['architecture']] | default(ansible_facts['architecture']) }}"
        description: Release architecture suffix, derived from the host architecture.
      node_exporter_release_url:
        type: str
        default: "https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}"
        description: Base URL holding the release tarball and sha256sums.txt; override for a mirror.
      node_exporter_binary_path:
        type: path
        default: /usr/local/bin/node_exporter
        description: Where the binary is installed.
      node_exporter_user:
        type: str
        default: node_exporter
        description: System user the service runs as.
      node_exporter_group:
        type: str
        default: node_exporter
        description: System group the service runs as.
      node_exporter_listen_address:
        type: str
        default: "0.0.0.0:9100"
        description: Address and port for the metrics endpoint.
      node_exporter_collectors_enabled:
        type: list
        elements: str
        default: []
        description: Collectors to enable in addition to the defaults.
      node_exporter_collectors_disabled:
        type: list
        elements: str
        default: []
        description: Default collectors to disable.
```

Use `type: bool` for booleans, `choices:` for closed sets, `elements:` for every list, and
`required: true` only for an input with no default.

## Templates

`templates/node_exporter.service.j2`:

```jinja
{{ ansible_managed | comment }}
[Unit]
Description=Prometheus node_exporter
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User={{ node_exporter_user }}
Group={{ node_exporter_group }}
EnvironmentFile=-/etc/default/node_exporter
ExecStart={{ node_exporter_binary_path }} $NODE_EXPORTER_OPTS
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

`templates/node_exporter.default.j2`:

```jinja
{{ ansible_managed | comment }}
NODE_EXPORTER_OPTS="--web.listen-address={{ node_exporter_listen_address }} --collector.textfile.directory=/var/lib/node_exporter/textfile
{%- for collector in node_exporter_collectors_enabled %} --collector.{{ collector }}{% endfor %}
{%- for collector in node_exporter_collectors_disabled %} --no-collector.{{ collector }}{% endfor %}"
```

## Windows

Same layout; `vars/Windows.yml`, and modules from `ansible.windows` /
`community.windows`:

- install: `ansible.windows.win_package` with `product_id` so a re-run is a no-op, or
  `chocolatey.chocolatey.win_chocolatey` with a pinned `version`;
- configure: `ansible.windows.win_template`;
- service: `ansible.windows.win_service` with `state: started` and `start_mode: auto`.

Gate Linux-only and Windows-only includes with
`when: ansible_facts['os_family'] == 'Windows'` (or `!=`).

## README.md and CHANGELOG.md

README in English: purpose, requirements, a variables table matching
`argument_specs.yml`, an example playbook and the tag list.

````markdown
# node_exporter

Installs Prometheus node_exporter from the GitHub release tarball and runs it as a
systemd service.

## Requirements

- Debian 12/13 or Ubuntu 24.04
- ansible-core 2.19 or later

## Role variables

| Variable | Default | Description |
|---|---|---|
| `node_exporter_version` | `1.9.1` | Release version to install |
| `node_exporter_listen_address` | `0.0.0.0:9100` | Metrics endpoint address |

## Example playbook

```yaml
- name: Install node_exporter
  hosts: monitored
  become: true
  roles:
    - role: node_exporter
      vars:
        node_exporter_version: "1.9.1"
```

## Tags

- `node_exporter`: everything
- `node_exporter_install`, `node_exporter_configure`, `node_exporter_service`: one stage
````

`CHANGELOG.md` starts with a `# Changelog` heading and a section dated with today's ISO
date (`## 2026-11-02`) listing the initial features.
