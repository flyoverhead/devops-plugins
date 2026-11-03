---
type: regex
target: {source: file, path: roles/chrony/tasks/main.yml}
flags: m
---

^- name: Read chrony version\s*$
