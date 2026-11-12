# Changelog

## 2026-11-11

### Added

- Skill `variant-analysis`: takes one confirmed bug (`path:line` plus the reason) and finds the other places with the same root cause. Writes a root-cause statement (or broken invariant), lists search axes, proves an exact-match pattern first, widens it one element at a time with `rg` and local Semgrep rules while recording every version, triages each candidate with separate severity and confidence, and writes an eight-section report to `$TMPDIR/variants-<repo>-<short-sha>.md` ending in a Semgrep or `rg` regression guard. Chat answer gives a verdict per location, ruled-out candidates included.
- Static only: no edits, builds, runs or tests of the target. Semgrep uses local rule files with `--metrics=off`; registry packs only after the user agrees to the download. No CodeQL, no installs.
- Optional cross-repository spread with `gh search code --owner`, falling back to `rg` or Grep over local checkouts when `gh` is missing, unauthenticated or the host is not GitHub.
- Agent `axis-sweeper`: one axis per agent, at most five at once on repositories over about 40 source files; returns candidates with quoted code and a looks-protected / looks-unprotected flag, never a verdict. Its tools are Read, Grep, Glob and `gh search code` (never `--web`/`-w`); `git grep` is not among them.
- Semgrep taint templates `variant-taint-go`, `variant-taint-python`, `variant-taint-ts` (HTTP request values, CLI args and environment into shell, SQL, file and markup sinks), each with a `semgrep --test` file.
- References: root cause and axes (with sink table and GitHub Actions / GitLab CI / Ansible / Bash / Terraform starters), pattern ladder, triage, output template.
- `tests/test_plugin.py`; evals: a trigger, a shell-injection outcome with two real variants and two decoys, and a no-known-bug negative.
