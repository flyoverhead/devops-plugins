---
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
tags: [outcome]
---

/patching-bugs:patching-bugs target/ (snipvault): issue SV-14 says `snipvault save ../../x` with SNIPVAULT_HOME set writes x outside the vault directory; snippets should always stay inside it. fix SV-14 and commit it
