---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [trigger]
---

PingHandler in internal/probe passes the host query param to `sh -c`. we got bitten by this kind of thing once already, how would I make a semgrep rule for it so CI flags the next one?
