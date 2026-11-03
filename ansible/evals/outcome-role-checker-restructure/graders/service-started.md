---
type: regex
target: {source: file, path: roles/node_exporter/tasks/service.yml}
flags: m
---

(?=[\s\S]*^\s+state: started\s*$)(?=[\s\S]*^\s+enabled: true\s*$)
