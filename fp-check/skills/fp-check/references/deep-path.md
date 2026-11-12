# Deep path

Used for a bug routed deep at the start or escalated at checkpoint A or B. Everything already
learnt on the standard path goes into the first agent's context; nothing is redone.

## Contents

- Task graph
- Task rules
- Dispatching agents
- Phase 3: impact (yours)
- Phase 5: devil's advocate (yours)
- Gate review
- When a phase fails

## Task graph

Create these tasks per bug with TaskCreate, titles exactly as shown, and set the blocking
edges with TaskUpdate. `→` means "blocks".

```text
BUG #N - Phase 1.1: Trust boundaries and path
  → BUG #N - Phase 1.2: API contracts
  → BUG #N - Phase 1.3: Environment protections
  → BUG #N - Phase 1.4: Cross-references
1.2, 1.3, 1.4
  → BUG #N - Phase 2.1: Attacker control
  → BUG #N - Phase 2.2: Bounds proof
  → BUG #N - Phase 2.3: Race feasibility
2.1, 2.2, 2.3 → BUG #N - Phase 2.4: Adversarial synthesis
2.4
  → BUG #N - Phase 3.1: Real impact
  → BUG #N - Phase 3.2: Primary control or defence in depth
3.1, 3.2 → BUG #N - Phase 4.1: Pseudocode PoC
4.1
  → BUG #N - Phase 4.2: Executable PoC
  → BUG #N - Phase 4.3: Unit-test PoC
  → BUG #N - Phase 4.4: Negative PoC
4.2, 4.3, 4.4 → BUG #N - Phase 4.5: PoC verification
4.5 → BUG #N - Phase 5: Devil's advocate
5 → BUG #N - GATE REVIEW
```

## Task rules

- Mark a task `in_progress` when its work starts.
- Mark it `completed` only when concrete evidence for it is written down: `path:line`, a
  derivation, a file path. "Looked fine" does not complete a task.
- Never start a task whose blockers are open.

## Dispatching agents

| Phases | Agent (`subagent_type`) | Context to pass |
|---|---|---|
| 1.1–1.4 | `fp-check:data-flow-analyzer` | Step 0 record, class, alleged `path:line`, repo root, any S1 notes |
| 2.1–2.4 | `fp-check:exploitability-verifier` | Step 0 record, the full Phase 1 report, any S2 notes |
| 4.1–4.5 | `fp-check:poc-builder` | Step 0 record, Phase 1–3 results, language and build system, the absolute PoC directory `$TMPDIR/fp-check-<repo>/bug-<N>/` |

- One agent per bug per phase; one bug's phases run in order, different bugs run side by side.
- At most five agents running at once.
- Always the full plugin-qualified name; never a general-purpose agent.
- Dispatch the PoC builder only for a bug that passed phases 1–3. For one that failed, record
  4.1–4.5 as "not built — Phase K failed: <evidence>" yourself.
- Each agent returns a fixed-heading Markdown report. A SubagentStop hook sends an agent back
  if a heading is missing. Read the report, check its `path:line` claims against the code
  where the verdict depends on them, and copy the evidence into the task.

## Phase 3: impact (yours)

Not delegated. Using the Phase 2 attack scenario:

- **3.1 Real impact.** What the attacker ends up with: code execution as which user, which
  data, which privilege. Robustness-only outcomes are recorded as such.
- **3.2 Primary control or defence in depth.** Name the control that should stop this attack.
  If the flagged code is a backup layer and the primary control holds, say which line proves
  it holds.

## Phase 5: devil's advocate (yours)

The thirteen questions in `devils-advocate.md`, each answered, ending in
confirmed or debunked.

## Gate review

The six-gate table from the skill, filled from the task evidence. G1 fails if any task in the
graph completed without evidence.

## When a phase fails

A phase that disproves the claim (data never reaches the sink, no attacker control, the
arithmetic cannot overflow) is recorded with its evidence, and the remaining phases still run
to completion so the record is whole. Later phases note what they could and could not
establish given the earlier failure. The FALSE POSITIVE verdict is written only after the gate
review, never mid-graph.
