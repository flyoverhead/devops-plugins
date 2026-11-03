---
type: regex
target: {source: file, path: roles/chrony/tasks/main.yml}
flags: m
---

^\s*when: chrony_enabled == true\s*$
