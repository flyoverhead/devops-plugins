---
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
tags: [outcome]
---

/code-improver:code-improver {"target": "snapcache", "reviewer": {"kind": "skill", "name": "golang:review"}, "scope": ["snapcache/**"], "maxRounds": 3}
