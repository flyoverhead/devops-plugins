---
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
tags: [outcome]
---

need a semgrep rule that catches request data ending up in a shell via exec.Command with sh -c, like in PingHandler. put it under rules/ and make sure it actually works on a test file
