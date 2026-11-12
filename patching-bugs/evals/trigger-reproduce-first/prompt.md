---
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
tags: [trigger]
---

target/ is snipvault. ticket SV-14 says `snipvault save ../../escaped < note.txt` with SNIPVAULT_HOME set puts the file two folders above the vault. before anybody changes a line I want that shown on the build we have right now, and keep the raw output of the run so someone else can repeat it without me
