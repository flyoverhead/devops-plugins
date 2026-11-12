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

PASS only if every real gap comes with a concrete test that would kill it (an input, a call and the expected result), including:
1. a blocked card passed to `admit`, expecting `Err(Refusal::Blocked)`;
2. a fare larger than the balance passed to `charge`, expecting `Err(Refusal::ShortFare)`;
3. `pass_active(0)` expected false;
4. `queue_open` at `waiting == capacity` expected false;
5. a check of `gate.refused` after refusing a blocked card, and of `gate.served` after a successful charge (one test may cover several items).

FAIL if any item is missing or a gap is left with only a vague remedy such as "add more tests".
