---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [negative]
---

code scanning opened this alert on main, tell me if it's real or noise:

```json
{"number": 7, "state": "open", "rule": {"id": "go/weak-cryptographic-algorithm", "severity": "error", "description": "Use of a broken or weak cryptographic algorithm"}, "most_recent_instance": {"location": {"path": "main.go", "start_line": 74}, "message": {"text": "Sensitive data is hashed with MD5, a weak algorithm."}}}
```
