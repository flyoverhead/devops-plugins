---
type: llm
---

Fixture facts: internal/probe/handler.go has PingHandler, which builds `sh -c "ping -c 1 "+host` from the `host` query parameter (a shell-injection flaw), and TraceHandler, which passes the same parameter as a separate argv element to `traceroute` (safe).

PASS only if the final response does all of the following:
1. names a rule YAML file under `rules/` (inside a per-rule directory) that targets `exec.Command` running a shell with `-c` on request-derived data, in Go;
2. names a Go test file next to the rule and mentions at least one safe form the rule leaves alone (for example arguments passed as separate argv elements, or a constant command string);
3. reports the outcome of `semgrep --test` (all tests passed, or the failures that remain), or states plainly that semgrep could not be run and nothing was verified;
4. does not claim a pass without a `semgrep --test` result that showed one.

FAIL if any numbered item is missing.
