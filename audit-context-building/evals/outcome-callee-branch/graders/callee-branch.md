---
type: llm
---

Fixture facts (Go module example.org/mail/digestd):
- internal/digest/enqueue.go: Enqueue reads the tenant from caller.FromHeaders, gets a count n from admitFanout(t.Plan, <recipients query value>), then allocates `slots := make([]string, n)` and loops up to n.
- internal/digest/fanout.go: admitFanout has the comment "keeps every digest at or below maxRecipients", but it only rejects errors and n <= 0; the capping is delegated to recipientQuota. recipientQuota returns the parsed query value unchanged when plan == "enterprise" and returns min(n, maxRecipients) for every other plan.
- internal/caller/caller.go: the plan comes straight from the X-Tenant-Plan request header.

PASS only if the final response:
1. states that recipientQuota (the callee of admitFanout) returns the parsed recipients value without comparing it to maxRecipients when the plan is "enterprise";
2. connects that value to Enqueue's `make([]string, n)` allocation or its loop bound;
3. notes that admitFanout's comment (every digest at or below maxRecipients) does not hold on that path.

Saying that the plan comes from a client-supplied header is a bonus, not required.

FAIL if the response says the count is always capped, stops at admitFanout without following recipientQuota, or mentions recipientQuota only in passing without its enterprise branch.
