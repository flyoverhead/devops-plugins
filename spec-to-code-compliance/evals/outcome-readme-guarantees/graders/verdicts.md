---
type: llm
---

Fixture facts (Go module example.org/relay/hookrelay; README lists three guarantees):
- Fair use, 120 requests per minute per X-Client-ID: internal/limiter/limiter.go counts requests, but the middleware returns early and never counts when the request carries `X-Relay-Replay: 1`. Nothing strips or authenticates that header, so any client can send it and skip the limit. The guarantee is NOT fully met (partial or contradicted).
- Delivery log retention, 14 days: internal/deliverylog/store.go sets `keepFor = 336 * time.Hour` (336 hours = 14 days), Prune removes entries older than that, and main.go runs the pruner every 30 minutes. There is no override. The guarantee is met; a lag of up to one pruning interval, or prune results that are only logged, is acceptable.
- Constant-time signature comparison: internal/relay/signature.go computes the expected HMAC and compares with `sig == expected`, a plain string comparison, despite a doc comment that claims constant time. The guarantee is contradicted.

PASS only if the final response does all of the following:
1. reports the rate-limit guarantee as not fully met (partial, contradicted or an equivalent "does not hold on every path"), naming the `X-Relay-Replay` header (or the replay bypass) as the reason;
2. reports the retention guarantee as met / implemented;
3. reports the constant-time guarantee as contradicted / not met because of the `==` comparison.

FAIL if any of the three verdicts is missing or wrong, if the rate limit is reported as fully met, if retention is reported as violated or absent, or if the response says code was executed or requests were sent to establish a verdict.
