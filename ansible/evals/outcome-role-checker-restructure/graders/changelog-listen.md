---
type: regex
target: {source: file, path: roles/node_exporter/CHANGELOG.md}
flags: i
---

restart \| node_exporter[^#]{0,300}deprecat|deprecat[^#]{0,300}restart \| node_exporter
