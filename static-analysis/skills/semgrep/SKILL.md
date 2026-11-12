---
name: semgrep
description: Runs a local Semgrep security audit of a repository — detects languages, plans public registry packs (p/default, p/secrets, language packs) with broader packs and third-party rule repos as opt-ins, scans only after an explicit yes with --metrics=off, and merges findings into SARIF outside the repo. Use when asked for a semgrep scan, a deep SAST audit, registry or custom rulesets, or third-party semgrep rules. Not for reading SARIF — use static-analysis:sarif-parsing; not for writing a rule — use semgrep-rule-creator:semgrep-rule-creator.
argument-hint: "[target-dir] [output-dir]"
allowed-tools: Read Glob Grep AskUserQuestion TaskCreate TaskUpdate TaskList Bash(${CLAUDE_SKILL_DIR}/scripts/run-scans.sh:*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/merge_sarif.py:*) Bash(semgrep --version --disable-version-check) Bash(SSL_CERT_FILE=/etc/ssl/cert.pem semgrep --version --disable-version-check) Bash(jq:*) Bash(printenv TMPDIR) Bash(mkdir -p:*) Bash(git rev-parse:*)
---

Target: $ARGUMENTS

# Semgrep audit

A local, wider-than-CI Semgrep pass over one repository. You plan, the user approves, the
bundled runner scans, the bundled merger produces one SARIF file.

## Rules that do not bend

- **No scan before an explicit yes.** The request itself is not approval. A question, silence
  or "looks interesting" is not approval. Only "yes", "go", "proceed", "approved" or an
  equivalent reply to the plan counts. Quote it back before running anything.
- **Only the runner scans.** Never type a `semgrep scan` command yourself, never run a subset
  by hand after a runner failure, never hand scanning to a subagent.
- **Nothing leaves the machine but rule downloads.** Every semgrep call carries `--metrics=off`
  and `--disable-version-check` (the runner adds both). Never `--config auto`: it reports the
  project to the registry and picks rules you cannot list.
- **Never install anything** — not semgrep, not Python packages. If semgrep is missing, say so
  and suggest the user installs a pinned version (`pipx install semgrep==<version>` or
  `brew install semgrep`).
- **Output never goes inside the repository.** Raw output and cloned rule repos contain example
  secrets and would be committed by accident.
- **The only direct `semgrep` call is the version probe.** Never add `-o`/`--output`, a
  `--*-output=` flag or `--autofix` to it; the runner owns every output file.
- **Do not probe for Semgrep Pro.** Checking for a Pro login fetches packs before anyone
  approved anything. The `--pro` flag is added on the user's word alone: licensed, logged in.

## Steps

Create one task per step and keep them current. Step 3 is completed only by a real yes.

1. Preflight
2. Detect languages
3. Plan and approval gate
4. Run the approved plan
5. Merge and report

### 1. Preflight

- Target: the argument, else the current repository root (`git rev-parse --show-toplevel`),
  else the current directory. It must exist; resolve it to an absolute path once.
- Output directory: the user's path if given, else `$TMPDIR/semgrep-<repo>_N` (`/tmp` when
  `TMPDIR` is unset), where `N` is one more than the highest existing suffix. Resolve it once,
  absolute, and `mkdir -p` it. Refuse a path inside the target.
- Semgrep: `semgrep --version --disable-version-check`. If that prints
  `ca-certs: no trust anchor file found`, it is the macOS sandbox, not a missing install:
  retry with `SSL_CERT_FILE=/etc/ssl/cert.pem` (the runner does the same). Not found → stop
  with the install hint above.
- `jq` and `python3` (3.11+) must be present; the runner and merger need them.

### 2. Detect languages

Use the Glob tool, never a shell `find`, with `**/` patterns so sub-projects in a monorepo
count. Count files per language and list the counts in the plan. The extension list, the YAML
and JSON rules and the framework hints are in
[references/rulesets.md](references/rulesets.md#detecting-languages); it mirrors the runner's
include table, so change both together.

### 3. Plan and approval gate

Choose rulesets with [references/rulesets.md](references/rulesets.md):

- **Pre-selected:** `p/default`, `p/secrets`, and the language pack for every detected
  language (plus a framework pack when a manifest shows the framework).
- **Opt-in, unchecked:** broader registry packs and every third-party rule repository that
  matches a detected language. Never pre-select them and never add them silently.
- **Mode:** if the user did not choose, show both and mark `run-all` as the default:
  - `run-all` — every finding of every selected ruleset;
  - `important-only` — scan with `--severity WARNING --severity ERROR`, then keep
    `category=security` with medium or high confidence and impact. INFO-severity rules,
    third-party ones included, are dropped at scan time, before the metadata filter.

Present the plan in one message, in this shape, then stop and wait:

```text
Semgrep scan plan
Target:      /abs/path/to/repo
Output:      /abs/tmp/semgrep-repo_1   (outside the repo)
Engine:      Semgrep OSS, --metrics=off; single-file analysis, no cross-file taint
Mode:        [x] run-all   [ ] important-only
Languages:   go (14 files), dockerfile (1), yaml (6; github-actions 2)

Rulesets
  [x] p/default            registry, baseline
  [x] p/secrets            registry, baseline
  [x] p/golang             registry, go
  [x] p/dockerfile         registry, dockerfile
  [ ] p/security-audit     registry, opt-in (noisier)
  [ ] https://github.com/trailofbits/semgrep-rules   third-party clone, AGPL-3.0, opt-in

Downloads on approval
  - registry packs from semgrep.dev: p/default, p/secrets, p/golang, p/dockerfile
  - git clones from GitHub: none unless you tick one
No source code is uploaded. Reply "yes" to run, or edit the list.
```

- Anything the user already asked for (a mode, a pack, a third-party repo) is shown ticked.
- Every download is listed: each registry pack, and each clone with its licence or
  "checked after clone" when the licence is not known up front.
- User edits → apply them and present the whole plan again. Approval covers exactly what the
  last plan showed; anything added later needs a new yes.
- The user may say they have Semgrep Pro and are logged in: add `--pro` and change the
  engine line (cross-file taint on). Otherwise report that cross-file taint was not analysed.

### 4. Run the approved plan

Write the approved plan to `<output>/rulesets.json` exactly as shown — this file is what the
runner reads, and it is not regenerated later. Changing it means going back to step 3.

```json
{"baseline": ["p/default", "p/secrets"], "go": ["p/golang"], "dockerfile": ["p/dockerfile"],
 "third_party": [], "local": []}
```

Keys: `baseline` and one lowercase key per detected language hold registry ids (`p/…`, `r/…`);
`third_party` holds https git URLs; `local` holds absolute directories of rules the user
supplied. Then run the runner once, in one Bash call:

```bash
"${CLAUDE_SKILL_DIR}/scripts/run-scans.sh" --target "$TARGET" --output-dir "$OUTPUT_DIR" \
  --mode run-all --rulesets "$OUTPUT_DIR/rulesets.json"
```

Add `--pro` only with the user's say-so. `--jobs N` (default 4) and `--max-target-bytes N`
(default 20000000, `0` = no limit) are optional. `--dry-run` prints the commands.

Exit 0 prints the path of `scans.json`. A non-zero exit means nothing usable ran: report the
runner's message and stop. Do not hand-run semgrep, do not retry with changed arguments, do
not substitute `p/default` for a pack that failed.

### 5. Merge and report

Important-only mode first filters the raw JSON of every scan `scans.json` records as successful
(failed scans may have left truncated output) into a sibling `<stem>-important.json`, then
merges with `--important`. The filter cannot run on SARIF (it has no metadata), and redirecting
onto its own input truncates it:

```bash
jq -r '.scans[].json' "$OUTPUT_DIR/scans.json" | while IFS= read -r f; do
  jq -f "${CLAUDE_SKILL_DIR}/scripts/important-filter.jq" "$f" > "${f%.json}-important.json" || exit 1
done
```

Merge (always pass `--scans`; add `--important` in important-only mode):

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/merge_sarif.py" "$OUTPUT_DIR/raw" \
  "$OUTPUT_DIR/results/results.sarif" --scans "$OUTPUT_DIR/scans.json"
```

The merger drops failed scans, deduplicates on (rule, file, start line) and refuses to write
a zero-finding file when the important-only filter and the SARIF no longer line up. Check the
merged file parses and count it:

```bash
jq 'reduce .runs[] as $run (0; . + ($run.results | length))' "$OUTPUT_DIR/results/results.sarif"
```

Then delete the clones, guarded so an empty variable can never widen the delete:

```bash
[ -n "$OUTPUT_DIR" ] && [ -d "$OUTPUT_DIR/repos" ] && rm -rf "$OUTPUT_DIR/repos"
```

Write the report with [references/output-format.md](references/output-format.md). Totals come from the
merged SARIF, never from adding up per-scan counts: one finding hit by two rulesets is one row.

## Output layout

```text
$TMPDIR/semgrep-<repo>_N/
  rulesets.json        approved plan, the runner's input
  scans.json           per-scan outcome: success, partial, failure, skip, zero coverage
  raw/<lang>-<ruleset>.json|.sarif   per-scan output (cross-language rulesets use all-…)
  results/results.sarif              merged result
  repos/               third-party clones, deleted after the merge
```

## Excuses to reject

| Thought | Reality |
|---|---|
| "They asked for a scan, that is approval." | The gate is separate. Present the plan and wait. |
| "Mark the gate done to unblock the run." | Step 3 closes on a quoted yes, nothing else. |
| "The runner failed, I'll run semgrep myself." | Report the failure and stop. |
| "A pack failed, use p/default instead." | Report the failed pack; changes go back through the gate. |
| "These extra packs would help." | Offer them unticked; never add them silently. |
| "Skip deleting repos/, it's in tmp." | Clones hold example secrets; delete after merging. |
| "Pick the output directory later." | Resolve it once in step 1; the plan shows it. |

## Near misses

- Existing SARIF to read, filter, diff or gate on → `static-analysis:sarif-parsing`.
- Interprocedural taint through a build → `static-analysis:codeql`.
- Write a new rule → `semgrep-rule-creator:semgrep-rule-creator`; port one to another language
  → `semgrep-rule-variant-creator:semgrep-rule-variant-creator`.
- Is a scanner finding or a GitHub code-scanning alert real? → `fp-check:fp-check`.
- Review Go changes before a pull request → `golang:review`; security review of a PR or commit
  range → `differential-review:differential-review`.
- CVEs, Dependabot, `govulncheck` or Trivy reports →
  `vulnerability-triage-brocards:vulnerability-triage-brocards`.
- Secrets in git history: no skill here covers it; say so (gitleaks or trufflehog are the
  usual tools).
