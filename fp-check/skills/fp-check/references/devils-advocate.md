# Devil's advocate

Argue against your own conclusion before the gate review. Answer every question in writing,
one or two lines each, citing `path:line` where code settles it.

## Standard path: seven-question spot-check (S5)

Against the finding:

1. Did I match a pattern instead of tracing this specific path?
2. Did I put a trust boundary in the wrong place, treating trusted data as hostile?
3. Is every step of my proof actually shown, or did I wave at one?
4. Am I calling a missing extra layer a vulnerability while the primary control holds?
5. Am I seeing a bug because I was asked to find one?

For the finding:

6. Am I rejecting it only because the exploit is complicated?
7. Did I credit a mitigation I have not read in the code? Re-read the sink and its callers now.

Any question you cannot settle is checkpoint B: move the bug to the deep path.

## Deep path: thirteen questions (Phase 5)

Against the finding:

1. Is the verdict resting on pattern similarity anywhere?
2. Did Phase 1 skip an upstream check or caller constraint?
3. Is any source labelled untrusted without its writer identified?
4. Is the bounds proof complete: every variable, every constraint, every step?
5. Is the concurrency real in this program's threading model?
6. Is the impact a real security consequence or a robustness problem?
7. Is this defence in depth with the primary control intact?
8. Does an API contract or the language already exclude the class?
9. Does the environment block it entirely (not merely raise the bar)?
10. Does the PoC rely on a mock, a disabled check or a precondition the attacker cannot force?
11. Would the verdict change if I assumed I am biased toward finding bugs?

For the finding:

12. Did any phase dismiss a step because it was hard rather than impossible?
13. Is any mitigation in the reports unverified? Re-read the code it cites.

Close with one line: **confirmed** (the finding survives) or **debunked** (name the question
that broke it and its evidence).
