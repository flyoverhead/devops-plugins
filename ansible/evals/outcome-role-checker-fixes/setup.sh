#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p roles/chrony/{tasks,defaults,meta}
cat > roles/chrony/meta/main.yml <<'YAML'
---
galaxy_info:
  author: Example Author
  description: Manage chrony
  license: MIT
  min_ansible_version: '2.19'
  platforms:
    - name: Debian
      versions: [bookworm]
dependencies: []
YAML
cat > roles/chrony/defaults/main.yml <<'YAML'
---
chrony_servers: [ntp1.example.org]
YAML
cat > roles/chrony/tasks/main.yml <<'YAML'
---
- name: install chrony
  ansible.builtin.apt:
    name: chrony
    update_cache: True
  when: chrony_enabled == true
- name: main | read chrony version
  ansible.builtin.command: chronyd --version
  register: chrony_version
  changed_when: false
- name: Show version
  debug:
    msg: "{{ chrony_version.stdout }}"
YAML
