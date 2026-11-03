---
type: regex
target: {source: file, path: roles/node_exporter/tasks/install.yml}
match: not_contains
flags: m
---

[a-z]+ \| node_exporter
