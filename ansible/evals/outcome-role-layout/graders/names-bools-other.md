---
type: llm
focus: trace
---

Look only at the content the agent wrote (Write and Edit tool inputs) to files under roles/node_exporter/tasks/ and roles/node_exporter/handlers/ other than tasks/main.yml, tasks/install.yml, tasks/configure.yml, tasks/service.yml and handlers/main.yml (for example tasks/assert.yml). Ignore files the agent only read. PASS if, in their final content, every task and handler `name:` starts with a capital letter and contains no `<word> |` prefix, and every boolean value is lowercase `true` or `false` (no True, False, yes, no, on, off in any case). Also PASS if no such other file was written. FAIL otherwise.
