#!/usr/bin/env bash
set -euo pipefail
git init -q
r=roles/chrony
mkdir -p "$r"/{defaults,handlers,meta,tasks,templates}
cat > "$r/defaults/main.yml" <<'YAML'
---
chrony_servers:
  - 0.pool.ntp.org
  - 1.pool.ntp.org
chrony_timezone: Etc/UTC
chrony_service_enabled: true
YAML
cat > "$r/meta/main.yml" <<'YAML'
---
galaxy_info:
  author: Example Author
  description: Install and configure chrony
  license: MIT
  min_ansible_version: '2.17'
  platforms:
    - name: Debian
      versions: [bookworm, trixie]
    - name: Ubuntu
      versions: [noble]
dependencies: []
YAML
cat > "$r/meta/argument_specs.yml" <<'YAML'
---
argument_specs:
  main:
    short_description: Install and configure chrony
    options:
      chrony_servers:
        type: list
        elements: str
        description: NTP servers.
        default: [0.pool.ntp.org, 1.pool.ntp.org]
      chrony_timezone:
        type: str
        description: System time zone.
        default: Etc/UTC
      chrony_service_enabled:
        type: bool
        description: Start and enable chronyd.
        default: true
YAML
cat > "$r/tasks/main.yml" <<'YAML'
---
- name: Include install tasks
  ansible.builtin.include_tasks:
    file: install.yml
    apply:
      tags: [chrony, chrony_install]
  tags: [chrony, chrony_install]

- name: Include configure tasks
  ansible.builtin.include_tasks:
    file: configure.yml
    apply:
      tags: [chrony, chrony_configure]
  tags: [chrony, chrony_configure]

- name: Include service tasks
  ansible.builtin.include_tasks:
    file: service.yml
    apply:
      tags: [chrony, chrony_service]
  tags: [chrony, chrony_service]
YAML
cat > "$r/tasks/install.yml" <<'YAML'
---
- name: Install chrony package
  ansible.builtin.apt:
    name: chrony
    state: present
    update_cache: true
    cache_valid_time: 3600

- name: Read chrony version
  ansible.builtin.command: chronyd --version
  register: chrony_version_output
  changed_when: false

- name: Show chrony version
  ansible.builtin.debug:
    msg: "{{ chrony_version_output.stdout }}"
YAML
cat > "$r/tasks/configure.yml" <<'YAML'
---
- name: Set time zone
  community.general.timezone:
    name: "{{ chrony_timezone }}"

- name: Template chrony.conf
  ansible.builtin.template:
    src: chrony.conf.j2
    dest: /etc/chrony/chrony.conf
    owner: root
    group: root
    mode: '0644'
  notify: Restart chrony
YAML
cat > "$r/tasks/service.yml" <<'YAML'
---
- name: Start and enable chrony
  ansible.builtin.systemd_service:
    name: chrony
    state: started
    enabled: true
  when: chrony_service_enabled
YAML
cat > "$r/handlers/main.yml" <<'YAML'
---
- name: Restart chrony
  ansible.builtin.systemd_service:
    name: chrony
    state: restarted
YAML
cat > "$r/templates/chrony.conf.j2" <<'J2'
{{ ansible_managed | comment }}
{% for server in chrony_servers %}
pool {{ server }} iburst
{% endfor %}
driftfile /var/lib/chrony/chrony.drift
makestep 1.0 3
rtcsync
J2
printf '# chrony\n\nInstalls and configures chrony.\n' > "$r/README.md"
printf '# Changelog\n\n## 2026-10-30\n\n- Initial role.\n' > "$r/CHANGELOG.md"
git add -A
git -c user.name='Example Author' -c user.email=author@example.org -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm 'Add chrony role'
