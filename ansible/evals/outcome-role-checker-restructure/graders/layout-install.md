---
type: regex
target: {source: file, path: roles/node_exporter/tasks/install.yml}
flags: m
---

(?=[\s\S]*--version)(?=[\s\S]*^\s+check_mode: false\s*$)(?=[\s\S]*^\s+changed_when: false\s*$)
