---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [negative]
---

recipientQuota in internal/digest/fanout.go hands back the raw count with no cap when X-Tenant-Plan is "enterprise". find me every other spot in this repo that drops a limit or check because of that plan header
