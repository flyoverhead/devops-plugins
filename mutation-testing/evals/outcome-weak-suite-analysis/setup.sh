#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Ines Duarte" GIT_AUTHOR_EMAIL="ines@example.org"
export GIT_COMMITTER_NAME="Ines Duarte" GIT_COMMITTER_EMAIL="ines@example.org"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p src tests

cat > Cargo.toml <<'TOML'
[package]
name = "faregate"
version = "0.3.1"
edition = "2021"
publish = false
TOML

cat > mewt.toml <<'TOML'
db = "mewt.sqlite"

[log]
level = "info"

[targets]
include = ["src/**/*.rs"]
ignore = ["tests"]

[test]
cmd = "cargo test"
TOML

cat > src/lib.rs <<'RS'
pub struct Card {
    pub id: u32,
    pub blocked: bool,
    pub balance_cents: u64,
    pub rides_left: u32,
}

pub struct Gate {
    /// Paid passages, shown on the station display board.
    pub served: u64,
    /// Ids of refused blocked cards, listed on the same board for staff.
    pub refused: Vec<u32>,
}

#[derive(Debug, PartialEq)]
pub enum Refusal {
    Blocked,
    ShortFare,
}

/// Refuses a card that the operator has blocked (reported lost or stolen).
pub fn admit(gate: &mut Gate, card: &Card) -> Result<(), Refusal> {
    if card.blocked {
        gate.refused.push(card.id);
        return Err(Refusal::Blocked);
    }
    Ok(())
}

/// Takes the fare from the stored balance; refuses when the balance is short.
pub fn charge(gate: &mut Gate, card: &mut Card, fare: u64) -> Result<u64, Refusal> {
    if fare > card.balance_cents {
        return Err(Refusal::ShortFare);
    }
    card.balance_cents -= fare;
    gate.served += 1;
    Ok(card.balance_cents)
}

/// True while the card still holds prepaid rides; the gate then skips the fare.
pub fn pass_active(rides_left: u32) -> bool {
    rides_left > 0
}

/// The gate keeps accepting taps while fewer than `capacity` riders wait.
pub fn queue_open(waiting: usize, capacity: usize) -> bool {
    waiting < capacity
}
RS

cat > tests/gate.rs <<'RS'
use faregate::*;

#[test]
fn open_card_is_admitted() {
    let mut gate = Gate { served: 0, refused: Vec::new() };
    let card = Card { id: 7, blocked: false, balance_cents: 500, rides_left: 0 };
    assert_eq!(admit(&mut gate, &card), Ok(()));
}

#[test]
fn fare_is_deducted() {
    let mut gate = Gate { served: 0, refused: Vec::new() };
    let mut card = Card { id: 8, blocked: false, balance_cents: 1000, rides_left: 0 };
    assert_eq!(charge(&mut gate, &mut card, 250), Ok(750));
}

#[test]
fn pass_with_rides_is_active() {
    assert!(pass_active(3));
}

#[test]
fn empty_queue_is_open() {
    assert!(queue_open(0, 10));
}
RS

cat > mewt-status.txt <<'TXT'
== mewt 4.0.0 status | db mewt.sqlite ==

[src/lib.rs] language=rust
  mutants: total=37 tested=31 untested=6
  results: caught=22 uncaught=9 timeout=0 skipped=6
  severity  caught/tested  rate
  high      2/2            100.0%
  medium    8/14           57.1%
  low       12/15          80.0%

[campaign] targets=1
  mutants: total=37 tested=31 untested=6
  results: caught=22 uncaught=9 timeout=0 skipped=6
  catch rate: 22/31 = 71.0%
TXT

cat > mewt-results.json <<'JSON'
{
  "results": [
    {"mutant": {"id": 3, "target_id": 1, "mutation_slug": "IF", "old_text": "card.blocked", "new_text": "false", "byte_offset": 545, "line_offset": 23}, "outcome": {"mutant_id": 3, "status": "Uncaught", "duration_ms": 4120, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:14:00Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}},
    {"mutant": {"id": 5, "target_id": 1, "mutation_slug": "CR", "old_text": "gate.refused.push(card.id);", "new_text": "// gate.refused.push(card.id);", "byte_offset": 568, "line_offset": 24}, "outcome": {"mutant_id": 5, "status": "Uncaught", "duration_ms": 3987, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:16:17Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}},
    {"mutant": {"id": 6, "target_id": 1, "mutation_slug": "CR", "old_text": "return Err(Refusal::Blocked);", "new_text": "// return Err(Refusal::Blocked);", "byte_offset": 604, "line_offset": 25}, "outcome": {"mutant_id": 6, "status": "Uncaught", "duration_ms": 4051, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:18:34Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}},
    {"mutant": {"id": 11, "target_id": 1, "mutation_slug": "IF", "old_text": "fare > card.balance_cents", "new_text": "false", "byte_offset": 825, "line_offset": 32}, "outcome": {"mutant_id": 11, "status": "Uncaught", "duration_ms": 4233, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:20:51Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}},
    {"mutant": {"id": 13, "target_id": 1, "mutation_slug": "CR", "old_text": "return Err(Refusal::ShortFare);", "new_text": "// return Err(Refusal::ShortFare);", "byte_offset": 861, "line_offset": 33}, "outcome": {"mutant_id": 13, "status": "Uncaught", "duration_ms": 4102, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:22:08Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}},
    {"mutant": {"id": 17, "target_id": 1, "mutation_slug": "CR", "old_text": "gate.served += 1;", "new_text": "// gate.served += 1;", "byte_offset": 935, "line_offset": 36}, "outcome": {"mutant_id": 17, "status": "Uncaught", "duration_ms": 3940, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:24:25Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}},
    {"mutant": {"id": 22, "target_id": 1, "mutation_slug": "COS", "old_text": ">", "new_text": "!=", "byte_offset": 1125, "line_offset": 42}, "outcome": {"mutant_id": 22, "status": "Uncaught", "duration_ms": 3876, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:26:42Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}},
    {"mutant": {"id": 24, "target_id": 1, "mutation_slug": "COS", "old_text": ">", "new_text": ">=", "byte_offset": 1125, "line_offset": 42}, "outcome": {"mutant_id": 24, "status": "Uncaught", "duration_ms": 4310, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:28:59Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}},
    {"mutant": {"id": 30, "target_id": 1, "mutation_slug": "COS", "old_text": "<", "new_text": "<=", "byte_offset": 1280, "line_offset": 47}, "outcome": {"mutant_id": 30, "status": "Uncaught", "duration_ms": 3902, "output": "running 4 tests\ntest result: ok. 4 passed; 0 failed; 0 ignored", "time": "2026-11-04T21:30:16Z"}, "target": {"id": 1, "path": "src/lib.rs", "language": "rust", "file_hash": "1d1b39832d4f28c35293946da3d9a617da01bc66e030c3f41b15cd1b24038969"}}
  ]
}
JSON

git add -A
git commit -q -m "faregate: gate decisions and mewt campaign results"
