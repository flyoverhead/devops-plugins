---
type: regex
target: {source: file, path: roles/node_exporter/handlers/main.yml}
flags: m
---

^- name: Restart node_exporter\s*$
