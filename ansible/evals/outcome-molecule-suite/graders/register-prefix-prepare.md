---
type: regex
target: {source: file, path: roles/chrony/molecule/default/prepare.yml}
match: not_contains
flags: m
---

^\s+register:\s*(?!chrony_)\w+
