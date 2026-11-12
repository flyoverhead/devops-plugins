# Changelog

## 2026-11-11

### Added

- Skill `fp-check`: per-finding TRUE or FALSE POSITIVE verdicts for security findings tied to a code location. Takes SARIF, gosec/semgrep/bandit style lists, findings files, review-skill findings and pasted GitHub code-scanning alert JSON (never fetched). Step 0 claim restatement, class lookup, a standard path (S1–S6, two escalation checkpoints) and a deep path (task graph with blocking edges, phases 1–5), a six-gate review, an exploit-chain pass for batches, a completeness check and a closing summary. Read-only on the repository; PoCs only under `$TMPDIR/fp-check-<repo>/bug-<N>/`, run only after an explicit yes naming the command. Dependency CVEs route to `vulnerability-triage-brocards:vulnerability-triage-brocards`; fix requests are told there is no fixing target.
- Skill-scoped SubagentStop prompt hook (30 s) that sends a phase agent back when its report lacks a required section.
- Agents `data-flow-analyzer` (Phase 1), `exploitability-verifier` (Phase 2), both Read/Grep/Glob, and `poc-builder` (Phase 4), which writes PoCs into `$TMPDIR` and runs nothing.
- References: evidence rules with the thirteen false-positive checks, class-specific questions, the deep-path task graph, phase procedures with report templates, and the devil's-advocate questions.
- `tests/test_plugin.py`: reference links, frontmatter, read-only tool lists, hook shape, agent report headings.
- Evals: two triggers (findings file, pasted code-scanning alert), a two-finding outcome with no-edit, no-write (only files under the temp-root PoC directory are excepted; the exemption is anchored at both ends and refuses `..`) and no-run graders, and negatives for a bug hunt and a dependency CVE.
- Hard limits forbid `--output`, `--ext-diff` and `--textconv` on `git log` and `git show`.
- Every documented `git diff`, `git show` and patch-showing `git log` passes `--no-ext-diff --no-textconv`.
