---
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Edit, Write]
tags: [negative]
---

quick one in target/: vault.Save and vault.Load take a name like ../x and happily leave SNIPVAULT_HOME. make them refuse names that climb out of the vault and add a unit test for it. no report or ceremony needed, just the change
