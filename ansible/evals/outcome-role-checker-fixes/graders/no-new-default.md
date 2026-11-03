---
type: regex
target: {source: file, path: roles/chrony/defaults/main.yml}
match: not_contains
flags: m
---

^chrony_enabled:
