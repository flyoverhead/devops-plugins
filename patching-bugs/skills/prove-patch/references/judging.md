# How a proof is judged

`verdict.py` applies these rules to the latest attempt. Know them before you plan, so the plan can
pass them honestly.

## Is the observation valid?

For every case run, on each side:

- the run finished (`exit_code` not null; null means timeout or kill);
- stdout has exactly one `PATCH_CASE` line whose payload has the keys `input` and `actual` only;
- that `input` equals the planned input, compared as JSON (key order does not matter);
- `PATCH_REACHED` appears once and is the last line.

Any miss is a gap for that case.

## Representative cases

| Baseline | Patched | Result |
|---|---|---|
| exit 0, or `actual` equals `expected` | anything | gap: the failure was never shown |
| non-zero, `actual` ≠ `expected` | exit 0, `actual` = `expected` | pass |
| non-zero, `actual` ≠ `expected` | non-zero, `actual` ≠ `expected` | finding: the fix does not hold |
| non-zero, `actual` ≠ `expected` | exit and `actual` disagree | gap |

## Control cases

| Baseline | Patched | Result |
|---|---|---|
| not (exit 0 with `actual` = `expected`) | anything | gap: the control is not a control |
| exit 0, `actual` = `expected` | exit 0, `actual` = `expected` | pass |
| exit 0, `actual` = `expected` | non-zero, `actual` ≠ `expected` | finding: the fix broke valid input |
| exit 0, `actual` = `expected` | exit and `actual` disagree | gap |

A bounded class needs at least two distinct representatives that fail on the baseline and one
valid control, all passing on the patch. Short of that, the report claims the exact example only.

## Project checks

| Situation | Result |
|---|---|
| patched did not finish | gap |
| no baseline run, kind `suite`, patched exit 0 | pass |
| no baseline run, any other case | gap |
| baseline exits non-zero | gap: the check proves nothing here |
| baseline 0, patched non-zero | finding |
| kind `behavior`, stdout differs between the sides | finding |
| otherwise | pass |

No project checks at all, or an empty `unproven` list, is a gap.

## Proof-wide gaps

- a planned case missing from `cases`, or a case id that is not planned, or a repeated id;
- an empty `argv`;
- a receipt path not in the manifest, or outside `receipts/`;
- `receipts/source.json` missing, its commits differing from `prove.json`, the reverted tree
  differing from the baseline tree, or the patched tree equal to the baseline tree;
- `prove.json` commits differing from `patch.json`;
- `reverted` other than `pass`; runtime `build_identity` other than `pass` (compile:
  `not_applicable`); a failure type different from the reproduction.

## Words to use

A gap means the evidence is missing or untrustworthy: report it as such, never as a pass or a
fail. A finding means the patched tree misbehaved under a valid observation: the fix needs another
attempt.
