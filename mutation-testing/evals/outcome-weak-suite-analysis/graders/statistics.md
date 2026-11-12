---
type: llm
---

Fixture facts (Rust crate `faregate`, `src/lib.rs`; `tests/gate.rs` has four tests: an unblocked card is admitted, charging 250 from 1000 returns 750, `pass_active(3)` is true, `queue_open(0, 10)` is true). `Gate` has two fields read by the station board: `served` (paid passages) and `refused` (ids of refused blocked cards). The saved mewt run has 37 mutants: 31 tested, 22 caught, 9 uncaught, 6 skipped, 0 timeouts. The 9 uncaught:
- line 23 IF `card.blocked` -> `false` and line 25 CR on `return Err(Refusal::Blocked);`: the blocked-card refusal in `admit` (access control);
- line 24 CR on `gate.refused.push(card.id);` in that branch (a record shown on the board);
- line 32 IF `fare > card.balance_cents` -> `false` and line 33 CR on `return Err(Refusal::ShortFare);`: the short-balance refusal in `charge` (money);
- line 36 CR on `gate.served += 1;` (a counter shown on the board);
- line 42 COS `rides_left > 0` -> `rides_left != 0` and -> `rides_left >= 0` (`rides_left` is `u32`);
- line 47 COS `waiting < capacity` -> `waiting <= capacity`.

The user asked for mutation-testing-report.md; judge the final response, which summarises it. Finding ids C-, H-, M- and L- stand for the first to fourth tier. Wording, formatting and tier labels such as "Critical" or "Tier 1" do not matter.

Labels such as "raw" or "adjusted" are optional, rounding to one decimal is fine, and a fraction such as 22/31 counts as stating the denominator.

PASS only if the statistics agree with 37 / 31 / 22 / 9 / 6: a raw kill rate of 22/31 (about 71.0 %) and an adjusted rate of 22/30 (about 73.3 %) that excludes the equivalent mutant, each with its denominator, and the skipped mutants not counted as caught or as tested. FAIL only on a wrong count or rate, a rate given without its denominator, or skipped mutants counted in a rate.
