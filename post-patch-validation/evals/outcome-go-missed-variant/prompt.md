---
max_turns: 70
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
tags: [outcome]
---

target/ is our auditlog repo. its last commit fixes AUD-212 (a newline in the actor field let a caller write a forged audit line) and tag `vulnerable` is the code right before it. validate that fix before I approve the PR. keep the plan and the results under ppv/ in this folder, not inside target/. you may build and run the Go code and its tests, and once the plan validates go ahead and run it without waiting for my ok
