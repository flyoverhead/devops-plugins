---
type: regex
target: {source: file, path: roles/chrony/tasks/main.yml}
match: not_contains
flags: m
---

^\s+debug:
