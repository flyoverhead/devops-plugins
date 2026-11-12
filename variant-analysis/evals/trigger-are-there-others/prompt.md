---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [trigger]
---

bug bounty report says ?pic= on /v1/thumb gets you a shell, see internal/imaging/thumb.go:16. I can fix that line in a minute, but did we write the same thing somewhere else in this repo?
