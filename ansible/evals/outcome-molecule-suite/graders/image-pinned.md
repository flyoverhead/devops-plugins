---
type: regex
target: {source: file, path: roles/chrony/molecule/default/molecule.yml}
match: not_contains
flags: m
---

^\s+image:\s*["']?(?!debian:\d+\.\d+["']?\s*$)(?![\w./-]+:[a-z]+-\d{8}["']?\s*$)(?![\w./-]+(?::[\w.-]+)?@sha256:[0-9a-f]{64}["']?\s*$)[\w./-]+(?::[^\s"'@]*)?(?:@[^\s"']*)?["']?\s*$
