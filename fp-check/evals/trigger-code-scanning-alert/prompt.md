---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [trigger]
---

this one is sitting open in code scanning for snapd and blocks the release checklist. copied the JSON from the alert page:

```json
{"number": 12, "state": "open", "created_at": "2026-11-09T08:41:17Z", "rule": {"id": "go/command-injection", "severity": "error", "security_severity_level": "critical", "description": "Command built from user-controlled sources"}, "tool": {"name": "CodeQL", "version": "2.19.3"}, "most_recent_instance": {"ref": "refs/heads/main", "state": "open", "location": {"path": "main.go", "start_line": 23, "end_line": 23, "start_column": 14, "end_column": 55}, "message": {"text": "This command depends on a user-provided value."}}}
```

does it hold up, or is it safe to dismiss?
