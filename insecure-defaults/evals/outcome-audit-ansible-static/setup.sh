#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p roles/ledger/{defaults,tasks,templates,handlers,meta}
cat > roles/ledger/README.md <<'MD'
# ledger

Installs the ledger API and its configuration.

## Variables

| Variable | Default | Notes |
|---|---|---|
| `ledger_db` | see `defaults/main.yml` | connection settings for Postgres |
| `ledger_master_key` | read from the secret store | encrypts stored statements |

## Testing

Dry-run against a host before applying:

    ansible-playbook -i inventories/stage site.yml --limit ledger --check --diff
MD
cat <<'DEFAULTS' > roles/ledger/defaults/main.yml
---
ledger_listen_port: 8443
ledger_db:
  host: 127.0.0.1
  port: 5432
  name: ledger
  user: ledger_app
  password: CHANGE_ME
ledger_master_key: "{{ lookup('community.hashi_vault.hashi_vault', 'secret=kv/data/ledger:master_key') }}"
DEFAULTS
cat > roles/ledger/tasks/main.yml <<'YAML'
---
- name: Create configuration directory
  ansible.builtin.file:
    path: /etc/ledger
    state: directory
    owner: root
    group: ledger
    mode: "0750"

- name: Render ledger configuration
  ansible.builtin.template:
    src: ledger.ini.j2
    dest: /etc/ledger/ledger.ini
    owner: root
    group: ledger
    mode: "0640"
  notify: Restart ledger

- name: Install master key
  ansible.builtin.copy:
    content: "{{ ledger_master_key }}"
    dest: /etc/ledger/master.key
    owner: root
    group: ledger
    mode: "0640"
  notify: Restart ledger
YAML
cat > roles/ledger/templates/ledger.ini.j2 <<'J2'
[server]
port = {{ ledger_listen_port }}

[database]
dsn = postgres://{{ ledger_db.user }}:{{ ledger_db.password }}@{{ ledger_db.host }}:{{ ledger_db.port }}/{{ ledger_db.name }}

[crypto]
master_key_file = /etc/ledger/master.key
J2
cat > roles/ledger/handlers/main.yml <<'YAML'
---
- name: Restart ledger
  ansible.builtin.systemd_service:
    name: ledger
    state: restarted
YAML
cat > roles/ledger/meta/main.yml <<'YAML'
---
galaxy_info:
  author: platform
  description: ledger API
  license: MIT
  min_ansible_version: "2.16"
dependencies: []
YAML
git add -A && git commit -q -m "ledger role"
