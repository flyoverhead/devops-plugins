---
max_turns: 20
allowed_tools: [Read, Glob, Grep, Skill]
tags: [trigger]
---

Format and Parse in amount.go turn cent counts into "12.05" style text and back. The single example test feels thin to me. How would I test them so they hold across every int64 and not only the handful of values I thought of?
