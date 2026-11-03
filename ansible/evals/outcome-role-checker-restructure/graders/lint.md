---
type: llm
focus: trace
---

PASS if, after the restructure edits, the transcript shows ansible-lint run on roles/node_exporter and its last run reports no failures (for example `0 failure(s)` or `Passed`, exit code 0), OR the agent reports that ansible-lint could not run (not installed or not importable) and states that the role is therefore not lint-verified. FAIL if the agent claims the role is lint-clean without a passing ansible-lint run, or if ansible-lint's last run still reports failures that the agent does not report.
