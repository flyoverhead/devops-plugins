# Finding the variant the fix missed

Read by the main agent and by `post-patch-validation:coverage-mapper` agents.

## Contents

- [Start from the cause, not the payload](#start-from-the-cause-not-the-payload)
- [Where variants hide](#where-variants-hide)
- [Per-lens checklist](#per-lens-checklist)
- [Harness choices by stack](#harness-choices-by-stack)
- [Arguments that do not count](#arguments-that-do-not-count)

## Start from the cause, not the payload

Write the root cause as one sentence before looking for variants: "user-controlled text reaches
the line writer and a raw line break ends the record". A variant is any other input or path
that satisfies the same sentence after the patch. Changing a literal, a byte count or a payload
length is not a variant unless that boundary is the cause.

Then ask what the patch actually enforces, read literally: which function, which branch, how
many times, on which inputs. The gap between "the cause sentence" and "what the patch enforces"
is where the variant is.

## Where variants hide

| Axis | Ask |
|---|---|
| Repetition and nesting | does the fix handle the second, third, nested or overlapping occurrence? A one-shot replace, a non-recursive strip or a single-pass decode usually does not |
| Sibling callers | who else calls the vulnerable helper, or a copy of it, without the new guard? |
| Alternate entry points | CLI, HTTP handler, batch import, message consumer, config reload |
| Alternate outputs | other writers, encoders, serializers or formatters that take the same value |
| Call style | callback versus direct versus streaming or chunked |
| Outcome paths | success, error, cancel, retry, timeout, teardown, deferred cleanup |
| Boundaries | empty, minimum, maximum, exactly-at-limit, repeated, mixed encodings |
| Ownership and lifetime | use after close, double release, shared buffers, stale references |
| Asymmetry | parser accepts what the serializer emits differently; normalise-then-check versus check-then-normalise |
| Concurrency | ordering between check and use, two writers, cancellation mid-way |

## Per-lens checklist

**root-cause**
- one proposal that reproduces the original assertion (`exploit`);
- at least one distinct variant from the table (`variant`), with the axis named;
- teardown and ownership paths of the changed code.

**behavior**
- benign output that must stay byte-identical (`behavior`), with a stream chosen;
- targeted regression commands (`regression`);
- remove time, randomness, addresses and unordered collections from what is compared.

**adjacent-security**
- what the patch touched that guards something else: cleanup, authorisation, bounds,
  concurrency, error handling, state;
- each proposal must pass on base, so a patched failure can be blamed on the patch.

**harness**
- the smallest native command that builds and drives the code;
- a benign `control` through the changed component;
- the project suite, a sanitizer build or a fixed-seed fuzz run (`suite`).

Each proposal states: id, kind, `covers`, rationale as a falsifiable sentence, and a strategy
written as argv plus input plus the assertion. Never claim a path is covered because the diff
mentions it; say which check exercises it, or list it as not covered with the reason.

## Harness choices by stack

| Stack | Typical harness |
|---|---|
| Go | a helper that runs `go run ./cmd/<tool>` from the checkout with crafted arguments and checks the output; existing tests through `go test -run '^TestName$' ./pkg/` |
| Python | `python3 {plan_dir}/checks/probe.py` importing the package from `$PPV_CHECKOUT` |
| Bash | run the script under test with crafted arguments in a scratch directory |
| TypeScript | `node` on the built output, or the project's test runner on one named test |
| Terraform | `terraform validate` with `-backend=false` init; source or build evidence only |
| Ansible | `ansible-playbook --syntax-check`, `ansible-lint`; source or build evidence only |
| GitHub Actions | syntax and expression review of the workflow; source evidence only, never a run |

Helpers never add files to the checkout; they may write only inside `$PPV_SCRATCH`.

## Arguments that do not count

| Heard | Answer |
|---|---|
| "The original PoC no longer works" | That proves one input. Test an independent variant |
| "It failed on base, so it reproduced" | Only with the marker printed and the failure being the assertion, not a build error |
| "The full suite passes" | The suite did not know about the bug; it says nothing about variants |
| "It matches the upstream patch" | Upstream can be incomplete too |
| "The diff is tiny" | Small diffs miss repeated and nested inputs most often |
| "All supplied checks passed" | Then say exactly that, with the evidence level; it is not "the fix is complete" |
| "No obvious variant" | Walk the axes above, or report the missing coverage as a gap |
