---
type: regex
target: {source: file, path: roles/node_exporter/tasks/service.yml}
match: not_contains
flags: m
---

^\s*- name:\s*['"]?([^A-Z'"\s]|[A-Za-z_]+ \| )
