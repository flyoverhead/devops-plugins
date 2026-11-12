---
type: llm
---

The README of the service has three numbered guarantees: fair use (rate limit), delivery log retention, and signature checks. Judge only these three; extra claims the response covers do not need to meet point 2.

PASS only if the final response does all of the following:
1. gives the path of a written report file located outside the repository (for example under /tmp, /private/tmp or /var/folders), or says the report could not be written and gives it in chat instead;
2. backs the verdict on each of the three numbered guarantees with at least one code location written as a file path with a line number or line range (for example `internal/limiter/limiter.go:41` or `store.go:10`);
3. says what was not checked, or states that nothing was left unchecked (a line such as "Not checked: nothing" counts).

FAIL if no report path is given and no reason is stated, if the report is said to be inside the repository, if any of the three numbered guarantees has no file:line evidence, or if the response says nothing at all about coverage.
