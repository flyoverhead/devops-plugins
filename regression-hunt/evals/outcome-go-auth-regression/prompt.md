---
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent, TaskStop, SendMessage]
tags: [outcome]
---

target/ is shelfctl, a little Go CLI of mine. It only lives on this machine, no remote, just local commits. Run a regression hunt on HEAD: did that commit break anything that worked before it? Prove whatever you find on real before and after builds, a code read isn't enough. Everything stays local. Put the campaign in campaign/. You may build and run the project's code, its tests and your PoCs on this machine without asking me again, and don't stop to ask me questions.
