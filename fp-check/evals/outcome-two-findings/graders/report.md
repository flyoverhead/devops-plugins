---
type: llm
---

Fixture facts for main.go:
- line 12: handleSnapshot reads the `label` query parameter; line 13 concatenates it into a shell string; line 14 runs that string with `exec.Command("sh", "-c", script)`. Nothing validates `label`. `/snapshot` is served on `:8085` (line 35) with no authentication, so any network client controls part of a shell command line.
- line 23: handleUsage runs `exec.Command("df", "-h", "/srv/exports")` with constant arguments and no shell; no request data reaches it.

findings.md lists finding 1 at main.go:14 and finding 2 at main.go:23.

PASS only if the final response does all of the following:
1. marks finding 1 (main.go:14, the `sh -c` call) TRUE POSITIVE, and traces the path from the `label` query parameter through the string concatenation into `sh -c`;
2. marks finding 2 (main.go:23, the `df` call) FALSE POSITIVE, with a reason based on the constant arguments or the absence of a shell or attacker-controlled data;
3. shows a gate review for each of the two findings that covers six gates (process, reachability, real impact, PoC validation, math bounds, environment), each with a pass/fail outcome (an explicit "N/A" style note with a pass is fine for math bounds);
4. ends with a summary that gives the counts (1 true positive, 1 false positive) and lists each finding.

FAIL if any numbered item is missing, if either verdict is reversed, or if the response says it ran a PoC, built or ran the service, or modified files in the repository.
