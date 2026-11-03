---
type: regex
target: {source: file, path: roles/chrony/molecule/default/verify.yml}
match: not_contains
flags: m
---

^\s+register:\s*(?!chrony_)\w+
