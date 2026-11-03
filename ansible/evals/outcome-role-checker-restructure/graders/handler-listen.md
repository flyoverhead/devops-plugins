---
type: regex
target: {source: file, path: roles/node_exporter/handlers/main.yml}
flags: m
---

^\s+listen:\s*(?:['"]restart \| node_exporter['"]|restart \| node_exporter|\[\s*['"]?restart \| node_exporter['"]?\s*\]|\n\s+-\s*['"]?restart \| node_exporter['"]?)\s*$
