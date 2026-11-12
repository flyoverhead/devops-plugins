---
max_turns: 20
allowed_tools: [Read, Write, Edit, Glob, Grep, Bash, Skill]
tags: [negative]
---

I'm about to rewrite Format to build the string without fmt.Sprintf. Add a benchmark that formats a 100-element slice of mixed amounts so I can compare allocs/op before and after the rewrite.
