# Semgrep audit output

Plain text, no emoji. Counts come from `results/results.sarif`. Read `scans.json` for the
conditional sections; print a section only when its condition holds.

## Always

```text
Semgrep audit — <repo>
Output:      <OUTPUT_DIR>
Mode:        run-all | important-only
Engine:      Semgrep OSS (cross-file taint not analysed) | Semgrep Pro (--pro)
Approved:    "<the user's words>"
Files:       <sum of filesScanned per language unit; "unknown" when -1>
Rulesets:    p/default, p/secrets, p/golang, ...
Findings:    <N> merged (ERROR <a>, WARNING <b>, INFO <c>)
By category: security <x>, correctness <y>, ...
Top rules:   <count>  <rule id>   (five lines)
Results:     <OUTPUT_DIR>/results/results.sarif
```

Severity comes from each result's level (`error`, `warning`, `note` map to ERROR, WARNING,
INFO). Category comes from the rule's `properties.tags` or the raw JSON metadata.

## Conditional sections

| `scans.json` field or event | What to say |
|---|---|
| `failed` non-empty | each ruleset with the first line of its error; its findings are not in the merge |
| `skipped` non-empty | each third-party repo and why (clone failed, no rules after pruning) |
| a scan with `partial: true` | exit 2: some rules did not compile; output is complete for the rest |
| `alsoShared` | rulesets that already ran unscoped in the baseline, so the language run was dropped |
| `unscoped` | language keys the runner has no glob table for: those packs saw the whole tree |
| `coveredNothing` | rulesets that matched zero files — a wrong-language plan reads as clean, so call it out |
| `oversized` | files over `maxTargetBytes` that semgrep skipped silently |
| merger printed `unparseable:` | the files named, and that their findings are missing |
| `excludePattern` non-empty | the pattern is unanchored and also hid any same-named directory in the repo |
| no `.semgrepignore` in the target | semgrep's built-in ignores skipped tests, vendored, minified and build output; that is not a clean result for those paths |

## Not covered

End with what the scan cannot see: cross-file data flow on the OSS engine, generated code,
files in languages without a selected ruleset, and anything excluded above.

For triage of individual findings point to `fp-check:fp-check`; to read or slice the merged
file later, `static-analysis:sarif-parsing`.
