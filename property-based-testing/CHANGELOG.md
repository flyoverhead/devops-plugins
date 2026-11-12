# Changelog

## 2026-11-11

### Added

- Skill `property-based-testing`: writes property tests for code with an algebraic shape, reviews existing property suites against a CRITICAL to LOW severity table, and triages shrunk counterexamples into code bug, wrong property, strategy artifact or ambiguous spec.
- Go native fuzz as the default for Go, `pgregory.net/rapid` only when `go.mod` already requires it, Hypothesis for Python and fast-check for TypeScript; the repo's existing library is always followed.
- Dependency gate: one offer naming the property it would enable, either answer accepted, and no edit to a manifest or install command without a yes.
- Pre-approved shell: `go test`, `go vet`, `rg`, `git ls-files`, `git rev-parse`. `python3 -m pytest` asks each time, since conftest.py and plugins run arbitrary code; `git grep` asks too. `## Limits` lists the forbidden `go test` flags (including `-blockprofile`, `-mutexprofile`, `-fuzzcachedir`), `rg --pre` and `git grep -O`.
- References for the property ladder, the rearrangements that expose a property, review and triage, and per-library idioms.
- `tests/test_plugin.py`; evals: a whole-input-space trigger, a Go outcome with no new dependency and a latent sign bug, and a benchmark negative.
