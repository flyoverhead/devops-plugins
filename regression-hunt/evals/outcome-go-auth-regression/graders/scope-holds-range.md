---
type: regex
target:
  source: file
  path: campaign/scope.json
pattern: '^(?=[\s\S]*"changes")(?=[\s\S]*(?:\b[0-9a-f]{40}\b[\s\S]*\b[0-9a-f]{40}\b|HEAD~1\.\.HEAD))'
arm: with-only
---
