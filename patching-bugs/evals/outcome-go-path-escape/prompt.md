---
max_turns: 90
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
tags: [outcome]
---

/patching-bugs:patching-bugs target/ is snipvault. SV-14, reported by Dana: `echo hi | SNIPVAULT_HOME=/some/dir snipvault save ../../escaped` writes the file two levels above /some/dir. Expected: every snippet (nested names like go/http.txt included) stays inside SNIPVAULT_HOME. Observed: the file lands outside it. You have my go-ahead to build and run the project's code, its tests, the PoC and your helper scripts without asking me again. Commit the fix locally, don't push anything.
