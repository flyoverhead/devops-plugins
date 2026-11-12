---
name: semgrep-rule-variant-creator
description: Carries a finished Semgrep rule over to further languages, each in its own cycle of applicability verdict, tests written first, AST-guided rule and a semgrep --test run; handles Go, Python, Bash, TypeScript, HCL, YAML, Dockerfile and any other language Semgrep parses. Use when someone wants an existing Semgrep or SAST rule ported, translated or adapted to another language, or the same detection for another stack. Not for a rule that does not exist yet — use semgrep-rule-creator:semgrep-rule-creator; not for scanning a repo with rules — use static-analysis:semgrep.
argument-hint: "<rule-file> <language...> [output-dir]"
allowed-tools: Read Write Edit Glob Grep AskUserQuestion Bash(semgrep --metrics=off:*) Bash(SSL_CERT_FILE=/etc/ssl/cert.pem semgrep --metrics=off:*) Bash(SEMGREP_ENABLE_VERSION_CHECK=0 semgrep show supported-languages) Bash(SSL_CERT_FILE=/etc/ssl/cert.pem SEMGREP_ENABLE_VERSION_CHECK=0 semgrep show supported-languages) Bash(command -v semgrep) Bash(mkdir -p:*) WebFetch(domain:semgrep.dev)
---

Request: $ARGUMENTS

# Porting a Semgrep rule, one language at a time

A port is a candidate for review. The same cycle writes the rule and its tests, so a green run
proves only that the two agree, not that the rule catches what matters in that ecosystem. Say so
in the final message.

## Inputs

Needed: the path of the rule file, and the target languages, one per entry ("Go and Java" is two).
Optional: an output directory. Ask for whatever is missing and nothing more. Without an output
directory, write beside the original rule; never inside an unrelated project tree.

Out of scope, mention in one sentence and carry on: fixing or widening the original rule, and
languages nobody named. A brand-new rule from a bug description belongs to
`semgrep-rule-creator:semgrep-rule-creator`, which is also the place for rule-writing basics
(taint versus patterns, tests first, narrowing).

## Ground rules

- **Say first.** One sentence on what is about to happen, before the first tool call.
- **Local only.** Every Semgrep run carries `--metrics=off --disable-version-check` and reads
  local files. Never `--validate`, `--config auto`, a `p/...` registry config, `semgrep login` or
  `semgrep ci`. The only network use is an optional page from semgrep.dev.
- **Read-only on the source.** The original rule and its tests are never edited. Only the
  variant directories are written.
- **Never install, upgrade or switch Semgrep.** Do not hunt for another build to get a green.
- **Foreground.** Semgrep runs are not backgrounded.
- On macOS, a crash about a missing CA trust anchor means prefixing the command with
  `SSL_CERT_FILE=/etc/ssl/cert.pem`.

## Limits

- Every `semgrep` run carries `--metrics=off --disable-version-check`.
- Never `-o`/`--output`, any `--*-output=` (`--sarif-output=`, `--json-output=` and the like) or
  `--autofix`. Results go to stdout; only the rule and test files are written, with Write.
- Never a remote `--config http://…` or `--config https://…`; configs are local paths.
- `semgrep show` rejects `--disable-version-check`; run it as
  `SEMGREP_ENABLE_VERSION_CHECK=0 semgrep show supported-languages`, the documented equivalent.

## Preflight

1. `command -v semgrep`. If nothing prints, still write every variant, state plainly that nothing
   was parsed or validated, and give the user the `--test` commands to run. Skip the rest.
2. `semgrep --metrics=off --disable-version-check --version`, recorded once before the first
   port. Every language uses that same binary.
3. Read the original rule and its test file. Note its mode, sources, sinks, sanitizers, the
   safe idioms its tests cover and any metadata.

## Cycle per language

Strictly sequential: finish the four phases for one language before starting the next. Never do
phase 2 for all languages and then phase 3 for all.

```text
- [ ] 1 Applicability
- [ ] 2 Tests
- [ ] 3 Translation
- [ ] 4 Validation
```

### 1. Applicability

Decide whether the detection means anything in the target. Questions and the verdict format are
in [applicability.md](references/applicability.md). Produce a verdict block:

```text
TARGET: <language>
VERDICT: APPLICABLE | APPLICABLE_WITH_ADAPTATION | NOT_APPLICABLE
REASONING: <why>
ADAPTATIONS_NEEDED: <only for adaptation>
EQUIVALENT_CONSTRUCTS: <original construct -> target construct, one per line>
```

Separately, and by running Semgrep, find out whether it can read the language at all
(`SEMGREP_ENABLE_VERSION_CHECK=0 semgrep show supported-languages`, then `--dump-ast -l <key>`
on a probe file). A language it cannot parse is reported as "Semgrep cannot analyze", never as
`NOT_APPLICABLE`, which claims the bug class is absent.

`NOT_APPLICABLE` is argued against once: is there a library or idiom that recreates the sink?
If the verdict survives, ask the user (AskUserQuestion) before dropping the language. A dropped
language gets no directory, no tests and no rule. A language's safety reputation is never the
reason; judge the specific construct.

### 2. Tests first

The test file is written before any rule exists, as
`<original-id>-<language>/<original-id>-<language>.<ext>` with the target's own extension
([workflow.md](references/workflow.md) lists them). Required: two or more `ruleid:` cases and two
or more `ok:` cases, in code a developer of that language would write. One `ok:` case must be the
language's native safe idiom, since that is the false positive people invent most. Put each
annotation on the line immediately above the code it grades. Use placeholders, never real
secrets, and keep the file short: one case per distinct construct or safe form.

### 3. Translation

Dump the AST of the new test file and write the pattern against the tree, not against source
resemblance. Translate the intent: re-choose sources, sinks and sanitizers from the target's own
ecosystem ([translation.md](references/translation.md)). Keep the original's mode; a taint rule
stays a taint rule. Changes to the YAML: `id` becomes `<original-id>-<language>`, `languages`
is the target key, and metadata gains `original-rule` and `ported-from`. Quote any pattern
containing ` : ` so YAML does not read it as a mapping.

### 4. Validation

```bash
semgrep --metrics=off --disable-version-check --test --config <dir>/<id>.yaml <dir>/<id>.<ext>
```

Success is a run that says all tests passed. If lines are missed, the pattern is too narrow for
the bug; if lines are flagged wrongly, it is too broad. Fix the rule, never the tests. After three failed fix rounds
stop that language and report failed validation with the last output. Before trusting a pass,
check that the rule really ran and that the test extension maps to the rule's language; the
checks that matter are in [workflow.md](references/workflow.md).

## Final message

Lead with one sentence: which languages passed, failed validation, were not applicable, or
cannot be analysed by Semgrep. Then per language, the directory and the `semgrep --test` result,
plus the Semgrep version used. Add a note only when a verdict changed, the target needed a shape
the original lacks, or tests would not go green. No per-iteration narration.
