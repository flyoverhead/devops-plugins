---
type: regex
target: {source: file, path: ppv/results/result.json}
weight: 2
---

"findings": \[[^\]]*"kind": "(?:variant|exploit)"
