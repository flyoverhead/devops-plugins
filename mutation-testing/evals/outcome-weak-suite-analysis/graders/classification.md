---
type: llm
weight: 2
---

Fixture facts (Rust crate `faregate`, `src/lib.rs`; `tests/gate.rs` has four tests: an unblocked card is admitted, charging 250 from 1000 returns 750, `pass_active(3)` is true, `queue_open(0, 10)` is true). `Gate` has two fields read by the station board: `served` (paid passages) and `refused` (ids of refused blocked cards). The saved mewt run has 37 mutants: 31 tested, 22 caught, 9 uncaught, 6 skipped, 0 timeouts. The 9 uncaught:
- line 23 IF `card.blocked` -> `false` and line 25 CR on `return Err(Refusal::Blocked);`: the blocked-card refusal in `admit` (access control);
- line 24 CR on `gate.refused.push(card.id);` in that branch (a record shown on the board);
- line 32 IF `fare > card.balance_cents` -> `false` and line 33 CR on `return Err(Refusal::ShortFare);`: the short-balance refusal in `charge` (money);
- line 36 CR on `gate.served += 1;` (a counter shown on the board);
- line 42 COS `rides_left > 0` -> `rides_left != 0` and -> `rides_left >= 0` (`rides_left` is `u32`);
- line 47 COS `waiting < capacity` -> `waiting <= capacity`.

The user asked for mutation-testing-report.md; judge the final response, which summarises it. Finding ids C-, H-, M- and L- stand for the first to fourth tier. Wording, formatting and tier labels such as "Critical" or "Tier 1" do not matter.

PASS only if all of these hold:
1. Line 42 is split: `!= 0` is equivalent because an unsigned value is never negative, and `>= 0` is a real gap because it differs at `rides_left == 0`.
2. The two blocked-card mutants (lines 23 and 25) are in the top tier.
3. The two short-balance mutants (lines 32 and 33) are real gaps in the second tier (or higher).
4. The two removed board updates (lines 24 and 36) are real gaps in a lower tier than lines 23 and 25, not equivalent.
5. Line 47 is a real gap.
6. All nine survivors are accounted for individually: eight real gaps and one equivalent mutant.

FAIL if any item does not hold.
