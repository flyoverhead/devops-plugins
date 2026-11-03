---
type: regex
target: {source: file, path: roles/chrony/molecule/default/molecule.yml}
---

(?=[\s\S]*privileged:\s*true)(?=[\s\S]*command:\s*["']{2})
