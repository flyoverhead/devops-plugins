---
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
tags: [outcome]
---

This is the faregate crate. Last week's mewt campaign is saved here as mewt-results.json and mewt-status.txt (mewt isn't installed on this machine, and I don't want it rerun). Go through every uncaught mutant, separate the ones no test could ever kill from the ones that point at a missing test, rank what's left by how much it matters, and write it up as a mutation-testing report. Leave the source, the tests and the result files as they are. Report header: project "Faregate", tool mewt 4.0.0. Don't ask me anything, make reasonable calls and note them.
