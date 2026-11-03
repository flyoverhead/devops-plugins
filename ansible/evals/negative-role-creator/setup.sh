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
chrony_enabled: True
chrony_servers: [ntp1.example.org]
YAML
cat > roles/chrony/tasks/main.yml <<'YAML'
---
- name: main | install chrony
  ansible.builtin.apt:
    name: chrony
  when: chrony_enabled == True
- name: Read chrony version
  ansible.builtin.command: chronyd --version
  register: chrony_version
  changed_when: False
- name: Show version
  ansible.builtin.debug:
    msg: "{{ chrony_version.stdout }}"
YAML
