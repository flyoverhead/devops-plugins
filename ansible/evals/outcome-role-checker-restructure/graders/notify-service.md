---
type: regex
target: {source: file, path: roles/node_exporter/tasks/service.yml}
match: not_contains
flags: m
---

[a-z]+ \| node_exporter
