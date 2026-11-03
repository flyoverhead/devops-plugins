---
type: regex
target: {source: file, path: openapi.yaml}
match: not_contains
flags: m
---

^\s{2}/(get|create|list|update|delete)[A-Z]
