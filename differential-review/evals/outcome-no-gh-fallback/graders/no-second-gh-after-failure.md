---
type: llm
---

Look at the tool calls in the transcript. A `gh` call is any Bash command whose program is `gh` (for example `gh pr view 7`).

PASS if there are no `gh` calls, or exactly one `gh` call and nothing after it retries `gh` in another form (another subcommand, flags, `--repo`, auth commands).

FAIL if a second `gh` call appears after the first one failed, or if any call to another code-host command-line tool appears.
