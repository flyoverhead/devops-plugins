---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [negative]
---

write a custom semgrep rule that flags exec.Command called with sh -c and a concatenated argument
