# Changelog

## 2026-11-11

### Added

- Skill `spec-to-code-compliance`: finds the documents that state intent (README guarantees, design notes, OpenAPI, doc comments, role `argument_specs`, Terraform variable descriptions, CI input text, `--help`) by content, quotes each requirement with its location, splits compound claims, takes force from the document's wording, ranks mandatory first and keeps the top 10 (up to 30 on request).
- Six verdicts (`implemented`, `partial`, `contradicted`, `stronger-than-spec`, `absent`, `undecidable`) with evidence rules: names are not proof, arithmetic is, `absent` needs a search log. Severity from critical to low by consequence.
- Agent `spec-compliance-checker`: one requirement per agent, at most five at a time; writes `requirements/<id>.md` and returns a verdict record.
- Agent `divergence-refuter`: two per divergence (code lens, document lens), read-only; either refutation drops the divergence, two failures make it unverified.
- Reverse-direction pass for reachable behaviour no document mentions.
- Report `$TMPDIR/spec-compliance-<repo>-<short-sha>/REPORT.md`; read-only on the repository, nothing executed, no network.
- References for document sources per stack (Go, Python, Bash, Ansible, Terraform, GitHub Actions, GitLab CI), verdicts and severity, three calibration cases and the file formats.
- `tests/test_plugin.py`; evals: a README-guarantees trigger, an outcome with three guarantees (one partial, one held by arithmetic, one contradicted) and a bug-hunt negative.
