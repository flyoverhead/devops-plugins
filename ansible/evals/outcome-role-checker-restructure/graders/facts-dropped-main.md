---
type: regex
target: {source: file, path: roles/node_exporter/tasks/main.yml}
match: not_contains
flags: m
---

node_exporter_(installed|update)\b|ansible_os_family
