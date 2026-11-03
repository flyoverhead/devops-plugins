#!/usr/bin/env bash
set -euo pipefail
git init -q
R=roles/node_exporter
mkdir -p $R/{defaults,vars,meta,tasks,handlers,templates}
cat > $R/meta/main.yml <<'YAML'
---
galaxy_info:
  role_name: node_exporter
  author: Example Author
  description: Install Prometheus node_exporter from the release tarball
  license: MIT
  min_ansible_version: '2.15'
  platforms:
    - name: Debian
      versions:
        - bookworm
    - name: EL
      versions:
        - '9'
  galaxy_tags:
    - monitoring
dependencies: []
YAML
cat > $R/defaults/main.yml <<'YAML'
---
node_exporter_version: '1.8.2'
node_exporter_arch: amd64
node_exporter_release_url: 'https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}'
node_exporter_download_url: '{{ node_exporter_release_url }}/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}.tar.gz'
node_exporter_binary_path: /usr/local/bin/node_exporter
node_exporter_user: node_exporter
node_exporter_group: node_exporter
node_exporter_listen_address: '0.0.0.0:9100'
node_exporter_textfile_dir: /var/lib/node_exporter/textfile
node_exporter_collectors_disabled: []
node_exporter_service_enabled: True
YAML
cat > $R/vars/Debian.yml <<'YAML'
---
node_exporter_nologin_shell: /usr/sbin/nologin
node_exporter_env_file: /etc/default/node_exporter
YAML
cat > $R/vars/RedHat.yml <<'YAML'
---
node_exporter_nologin_shell: /sbin/nologin
node_exporter_env_file: /etc/sysconfig/node_exporter
YAML
cat > $R/tasks/main.yml <<'YAML'
---
- name: main | include os vars
  include_vars: "{{ ansible_os_family }}.yml"
  tags: always

- name: main | detect
  include_tasks: detect.yml
  tags: node_exporter.detect

- name: main | install
  include_tasks: install.yml
  when: not node_exporter_installed
  tags: node_exporter.install

- name: main | update
  include_tasks: update.yml
  when: node_exporter_update
  tags: node_exporter.update

- name: main | config
  include_tasks: config.yml
  tags: node_exporter.config
YAML
cat > $R/tasks/detect.yml <<'YAML'
---
- name: detect | binary stat
  ansible.builtin.stat:
    path: "{{ node_exporter_binary_path }}"
  register: node_exporter_binary

- name: detect | set installed fact
  ansible.builtin.set_fact:
    node_exporter_installed: "{{ node_exporter_binary.stat.exists }}"

- name: detect | installed version
  ansible.builtin.command: "{{ node_exporter_binary_path }} --version"
  register: node_exporter_version_output
  changed_when: False
  when: node_exporter_installed

- name: detect | set update fact
  ansible.builtin.set_fact:
    node_exporter_update: >-
      {{ node_exporter_installed and node_exporter_version is version(
      (node_exporter_version_output.stdout ~ node_exporter_version_output.stderr)
      | regex_search('[0-9]+[.][0-9]+[.][0-9]+'), '>') }}
YAML
cat > $R/tasks/install.yml <<'YAML'
---
- name: install | create group
  group:
    name: "{{ node_exporter_group }}"
    system: yes

- name: install | create user
  user:
    name: "{{ node_exporter_user }}"
    group: "{{ node_exporter_group }}"
    shell: "{{ node_exporter_nologin_shell }}"
    system: yes
    create_home: no

- name: install | download archive
  get_url:
    url: "{{ node_exporter_download_url }}"
    dest: /tmp/node_exporter.tar.gz
    mode: '0644'

- name: install | unpack archive
  unarchive:
    src: /tmp/node_exporter.tar.gz
    dest: /tmp
    remote_src: True

- name: install | copy binary
  copy:
    src: "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}/node_exporter"
    dest: "{{ node_exporter_binary_path }}"
    remote_src: True
    mode: '0755'

- name: install | systemd unit
  template:
    src: node_exporter.service.j2
    dest: /etc/systemd/system/node_exporter.service
    mode: '0644'
  notify: restart | node_exporter

- name: install | start service
  systemd:
    name: node_exporter
    state: started
    enabled: True
    daemon_reload: True
  when: node_exporter_service_enabled == True
YAML
cat > $R/tasks/update.yml <<'YAML'
---
- name: update | stop service
  ansible.builtin.systemd:
    name: node_exporter
    state: stopped

- name: update | download archive
  ansible.builtin.get_url:
    url: "{{ node_exporter_download_url }}"
    dest: /tmp/node_exporter.tar.gz
    mode: '0644'
    force: True

- name: update | unpack archive
  ansible.builtin.unarchive:
    src: /tmp/node_exporter.tar.gz
    dest: /tmp
    remote_src: True

- name: update | replace binary
  ansible.builtin.copy:
    src: "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}/node_exporter"
    dest: "{{ node_exporter_binary_path }}"
    remote_src: True
    mode: '0755'
  notify: restart | node_exporter
YAML
cat > $R/tasks/config.yml <<'YAML'
---
- name: config | textfile directory
  ansible.builtin.file:
    path: "{{ node_exporter_textfile_dir }}"
    state: directory
    owner: "{{ node_exporter_user }}"
    group: "{{ node_exporter_group }}"
    mode: '0755'

- name: config | environment file
  ansible.builtin.template:
    src: node_exporter.env.j2
    dest: "{{ node_exporter_env_file }}"
    mode: '0644'
  notify: restart | node_exporter

- name: config | enable service
  ansible.builtin.service:
    name: node_exporter
    enabled: yes
  when: node_exporter_service_enabled == true
YAML
cat > $R/handlers/main.yml <<'YAML'
---
- name: restart | node_exporter
  ansible.builtin.systemd:
    name: node_exporter
    state: restarted
    daemon_reload: yes
YAML
cat > $R/templates/node_exporter.service.j2 <<'J2'
[Unit]
Description=Prometheus node_exporter
After=network-online.target
Wants=network-online.target

[Service]
User={{ node_exporter_user }}
Group={{ node_exporter_group }}
EnvironmentFile=-{{ node_exporter_env_file }}
ExecStart={{ node_exporter_binary_path }} $NODE_EXPORTER_ARGS
Restart=on-failure

[Install]
WantedBy=multi-user.target
J2
cat > $R/templates/node_exporter.env.j2 <<'J2'
NODE_EXPORTER_ARGS="--web.listen-address={{ node_exporter_listen_address }} --collector.textfile.directory={{ node_exporter_textfile_dir }}{% for c in node_exporter_collectors_disabled %} --no-collector.{{ c }}{% endfor %}"
J2
cat > $R/README.md <<'MD'
# node_exporter

Installs Prometheus node_exporter from the release tarball on Debian and EL hosts.
MD
cat > $R/CHANGELOG.md <<'MD'
# Changelog

## 2025-03-10

- Initial role.
MD
git add -A
git -c user.name='Example Author' -c user.email=author@example.org -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm 'Add node_exporter role'
