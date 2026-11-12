# Writing the run report and the handoff

Every run that got as far as `finding.json` ends with `<run>/report.md`, including failed and
inconclusive ones. Write `report-input.json` first; the report is built from it and the records.

## report-input.json

- `bug`: what goes wrong, from the receipts, not from the report's wording alone.
- `fix_why`: why this change restores the invariant; empty when there is no patch.
- `open_risks`: up to five, concrete (an exclusion, an unproven limit, a skipped stage).
- `include_poc`: true only when the bug is fixed or already public; an unfixed security bug keeps
  the PoC out of the report.
- `baseline_checks`: for a run that ended on the unchanged baseline (not reproduced), one item per
  case, pointing at the retained per-case stdout and `.exit.json` from `reproduce/receipts/` and
  `validate/receipts/`. A case with a missing or ambiguous receipt stays out and is called
  inconclusive in the report.

## report.md

```markdown
# <finding title>

Verdict: <READY | READY_WITH_CONCERNS | NOT_READY | NOT_REPRODUCED | INCONCLUSIVE>
Outcome: <repaired (bounded class | exact example) | inconclusive | no patch required>
Run: <run dir>   Baseline: <sha>   Patch commit: <sha or none, local only, not pushed>

## Bug
<bug>. Invariant: <invariant>. Claim breadth: <from verdict.py>.

## Evidence
| Stage | Agent | Result | Receipts |
|---|---|---|---|
| reproduce | reproducer@… | reproduced | reproduce/receipts/… |
| validate | validator@… | confirmed | validate/receipts/… |
| patch N | patcher-N@… | <sha>, variants fixed/not fixed | patch/attempt-N/ |
| prove N | prover-N@… | cases, checks, three-arm: <reverted>, identity: <build_identity> | prove/attempt-N/receipts/ |
| regression | … | <outcomes or "not run"> | regression/ |

## Why the fix holds
<fix_why>

## Open risks
- <open_risks and every verdict.py reason>

## PoC
<only when include_poc is true: the harness command and the planned inputs>
```

INCONCLUSIVE is used when `records.py check` fails, the before-repair gate fails, or evidence
cannot be trusted; quote the error.

## handoff.md

Only for READY and READY_WITH_CONCERNS; delete an older `handoff.md` when the new verdict is
anything else. For the maintainer who will review the local commit:

- the commit SHA and subject, `fix.patch` and `tests.patch` paths;
- how to rerun the regression test and the three-arm check (copy the commands from
  `receipts/<label>/launch.json` and from the prover's `arms.py run` call);
- the concerns, and that nothing has been pushed: pushing and opening a PR are theirs to do.
