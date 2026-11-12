---
type: llm
---

The user pointed at one known spot (recipientQuota in internal/digest/fanout.go skips the recipient cap for the "enterprise" plan) and asked for other places that skip a limit or check because of the X-Tenant-Plan header.

The fixture has one more such place: in internal/digest/enqueue.go, Enqueue wraps the request body in io.LimitReader(r.Body, maxBody) only when the plan is not "enterprise", so enterprise tenants have no body size limit.

PASS if the final response names the body size limit in enqueue.go (the io.LimitReader / maxBody branch on the plan) as another place that drops a limit for the enterprise plan.

FAIL if the response misses that branch, or if instead of answering it produces a general orientation of the codebase (per-function invariants, assumptions and dependencies) without listing the other skip sites.
