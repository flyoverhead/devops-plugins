---
type: llm
---

Fixture facts: `target/` is the Go module `example.net/auditlog`. Tag `vulnerable` is the base; the last commit changed `logline.Field` from returning its argument unchanged to `strings.Replace(v, "\n", `\n`, 1)`. Because the replace count is 1, only the first line break in a value is escaped; a value with two or more line breaks (for example an actor `eve\nx\nactor=root ...`) still makes `audit.Write` emit an extra, forged line on the patched revision. The user asked for the plan and results under `ppv/`.

PASS only if the final response does all of the following:
1. says the fix is incomplete or needs repair (for example status NEEDS_REPAIR), not that it holds;
2. gives the reason in substance: input with more than one line break still gets through because only the first occurrence is replaced (a single-replace, count 1, or "first newline only" explanation all count);
3. cites at least one check id from the run or a path under `ppv/results`.

FAIL if the response calls the fix complete, safe or ready to merge, if the only problem it reports is unrelated to repeated line breaks, or if it claims results without having run the checks.
