---
type: regex
target: {source: file, path: roles/chrony/molecule/default/molecule.yml}
flags: m
---

test_sequence:(?:\s*\n\s*-\s*\w+)*?\s*\n\s*-\s*converge\s*\n\s*-\s*idempotence\b
