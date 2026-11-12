---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [trigger]
---

semgrep put main.go:23 in findings.md as command injection. that line only runs df on a fixed path, I don't see how anyone gets input into it. am I right that it's bogus?
