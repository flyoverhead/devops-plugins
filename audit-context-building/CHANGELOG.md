# Changelog

## 2026-11-11

### Added

- Skill `audit-context-building`: four stages (orient, analyze, synthesize, hand over) that build written understanding of an unfamiliar repository before an audit, without verdicts. Orientation answers parts, ways in, actors and lasting state with cited lines, ranks units by how much correctness rests on them, and keeps the top 12 (or the user's count, or one named function).
- Agent `function-analyzer`: one per unit, at most five at a time, even for a single small unit. It reads every reachable callee on every path, treats callees without source as black boxes, writes `functions/NN-<name>.md` and returns a nine-key record. It refuses a brief without `tmpRoot`, an output path other than `<tmpRoot>/audit-context-<dir>/functions/NN-<name>.md`, and a path inside the repository, comparing paths without trailing slashes or a leading `/private`.
- `DOSSIER.md` built from the records: state map, flows, actor reach, hotspots, cross-unit invariants, disagreements, every `nothing found` assumption verbatim, open questions and the not-analysed list.
- Notes in `$TMPDIR/audit-context-<repo>-<short-sha>/`, or `audit-context-<dir>-nogit/` outside a git repository; an existing directory that already holds a `DOSSIER.md` gets a `-2`, `-3`, … suffix instead of being overwritten. Trailing slashes are stripped from the temp root. A failed agent dispatch stops the run; units are never analysed inline instead.
- References for per-stack orientation (Go, Python, TypeScript, Bash, Ansible, Terraform, GitLab CI) and the three file formats.
- `tests/test_plugin.py`; evals: an unfamiliar-repo trigger, an outcome that has to follow a callee's uncapped branch, and a variant-hunt negative.
