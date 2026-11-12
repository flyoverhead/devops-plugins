# Mutation Testing Report: Faregate

| | |
|---|---|
| Project | Faregate |
| Repository | `faregate` (local checkout) |
| Date | 2026-11-11 |
| Tool | mewt 4.0.0 |
| Analysed by | mutation-testing skill |

## Executive Summary

| Metric | Value |
|---|---|
| Mutants generated | 37 |
| Tested | 31 |
| Killed | 22 |
| Survived | 9 |
| Equivalent | 1 |
| Real gaps | 8 |
| Unresolved | 0 |
| Skipped / timed out | 6 / 0 |
| Raw kill rate | 22 / 31 = 71.0 % |
| Adjusted kill rate | 22 / 30 = 73.3 % |

The analysis covers the nine uncaught mutants in `src/lib.rs` from `mewt-results.json`, with totals
from `mewt-status.txt`. The six skipped mutants were never run and are in no rate. The findings
describe weaknesses in `tests/gate.rs`, not confirmed defects in the gate.

| Tier | Real gaps | Share |
|---|---|---|
| Tier 1 Critical | 2 | 25.0 % |
| Tier 2 High | 3 | 37.5 % |
| Tier 3 Medium | 1 | 12.5 % |
| Tier 4 Low | 2 | 25.0 % |

## Equivalent Mutants

| # | File | Line | Original → Mutated | Reason |
|---|---|---|---|---|
| 1 | `src/lib.rs` | 42 | `rides_left > 0` → `rides_left != 0` | `rides_left` is `u32`, so it is never negative and both expressions agree on every value |
| 2 | `src/lib.rs` | 42 | `rides_left > 0` → `rides_left >= 0` | the gate treats both as "has rides"; judged equivalent |

## Tier 1: Critical

### C-1: Blocked cards are never refused in a test

- **Location:** `src/lib.rs`, line 23
- **Mutation:** `card.blocked` → `false` (IF)
- **Context:** `admit` refuses cards reported lost or stolen; this is the gate's access check.
- **Tests that touch it:** `tests/gate.rs`: `open_card_is_admitted`
- **Why it survived:** the only test uses an unblocked card, so the refusal branch never runs.
- **Recommended test:** admit a card with `blocked` set and expect `Err(Refusal::Blocked)`.

### C-2: The refusal itself is unchecked

- **Location:** `src/lib.rs`, line 25
- **Mutation:** `return Err(Refusal::Blocked);` commented out (CR)
- **Context:** without the return a blocked card falls through to `Ok(())`.
- **Tests that touch it:** `tests/gate.rs`: `open_card_is_admitted`
- **Why it survived:** same as C-1; the branch is never entered.
- **Recommended test:** the C-1 test also kills this mutant.

## Tier 2: High

### H-1: Short balance is never charged in a test

- **Location:** `src/lib.rs`, line 32
- **Mutation:** `fare > card.balance_cents` → `false` (IF)
- **Context:** `charge` must refuse a fare larger than the stored balance; otherwise the
  subtraction underflows.
- **Tests that touch it:** `tests/gate.rs`: `fare_is_deducted`
- **Why it survived:** the only charge has a fare below the balance.
- **Recommended test:** charge 300 from a balance of 200 and expect `Err(Refusal::ShortFare)` with
  the balance unchanged; add a fare exactly equal to the balance, which must succeed.

### H-2: ShortFare refusal removed

- **Location:** `src/lib.rs`, line 33
- **Mutation:** `return Err(Refusal::ShortFare);` commented out (CR)
- **Context:** the same guard as H-1; removing the return lets the charge proceed.
- **Tests that touch it:** `tests/gate.rs`: `fare_is_deducted`
- **Why it survived:** the refusal path is never entered.
- **Recommended test:** the H-1 test kills this mutant.

### H-3: An exhausted pass still counts as active

- **Location:** `src/lib.rs`, line 42
- **Mutation:** `rides_left > 0` → `rides_left >= 0` (COS)
- **Context:** `pass_active` decides whether the fare is skipped; `>= 0` on `u32` is always true, so
  every card would ride free.
- **Tests that touch it:** `tests/gate.rs`: `pass_with_rides_is_active`
- **Why it survived:** only `pass_active(3)` is tested; the boundary value 0 is never used.
- **Recommended test:** assert that `pass_active(0)` is false.

## Tier 3: Medium

### M-1: Queue accepts one rider over capacity

- **Location:** `src/lib.rs`, line 47
- **Mutation:** `waiting < capacity` → `waiting <= capacity` (COS)
- **Context:** a capacity guard on the waiting queue.
- **Tests that touch it:** `tests/gate.rs`: `empty_queue_is_open`
- **Why it survived:** only an empty queue is tested.
- **Recommended test:** assert that `queue_open(10, 10)` is false.

## Tier 4: Low

### L-1: Refused card not listed on the board

- **Location:** `src/lib.rs`, line 24
- **Mutation:** `gate.refused.push(card.id);` commented out (CR)
- **Context:** `refused` feeds the staff list on the station board; display only.
- **Tests that touch it:** none reach the branch.
- **Why it survived:** the refusal branch never runs, so nothing reads `refused`.
- **Recommended test:** extend the C-1 test to assert that `gate.refused` holds the blocked card's id.

### L-2: Display counter not incremented

- **Location:** `src/lib.rs`, line 36
- **Mutation:** `gate.served += 1;` commented out (CR)
- **Context:** `served` feeds the station display only.
- **Tests that touch it:** `tests/gate.rs`: `fare_is_deducted`
- **Why it survived:** the test checks the returned balance, not the counter.
- **Recommended test:** after one successful charge, assert `gate.served == 1`.

## Recommendations

- `tests/gate.rs`, refusals: a blocked card (C-1, C-2) and a short balance plus the equal-balance
  boundary (H-1, H-2).
- `tests/gate.rs`, boundaries: `pass_active(0)` (H-3) and `queue_open(10, 10)` (M-1).
- `tests/gate.rs`, board fields: `gate.refused` after a refusal (L-1) and `gate.served` after a
  charge (L-2).

## Appendix

- **Inputs:** `mewt-results.json`, `mewt-status.txt`, `mewt.toml`, `src/lib.rs`, `tests/gate.rs`.
- **Survivors per source file:**

  | File | T1 | T2 | T3 | T4 | Equivalent | Unresolved |
  |---|---|---|---|---|---|---|
  | `src/lib.rs` | 2 | 3 | 1 | 2 | 1 | 0 |

- **Method:** survivors are tiered by the impact of the mutated code, not the mutation operator;
  equivalence was decided by type, reachability and downstream-use analysis plus an attempt to
  construct a distinguishing input.
