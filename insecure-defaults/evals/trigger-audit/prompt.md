---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [trigger]
---

before we ship this service can you go over it for insecure defaults? I'm mostly worried about stuff like a key that quietly turns into some hardcoded string when nobody set the env var
