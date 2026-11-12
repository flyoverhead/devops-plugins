---
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Edit, Write, Agent]
tags: [outcome]
---

infra/ has the terraform for our reports database and the ansible that sets up its hosts. check both for insecure defaults, prod applies terraform with prod.tfvars
