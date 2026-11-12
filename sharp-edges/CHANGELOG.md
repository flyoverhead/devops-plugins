# Changelog

## 2026-11-11

### Added

- Skill `sharp-edges`: read-only review of how easily an interface is misused — Go, Python and TypeScript APIs, CLI flags, env vars, Bash scripts, Ansible role variables, Terraform module inputs, GitHub Actions and GitLab CI workflows. Five steps: map choice points, probe degenerate values (`0`, `""`, null, `[]`, `-1`, wrong booleans, wrong-meaning and invalid values), picture three callers (adversary, copier, misreader), prove each finding with a minimal misuse and a traced `path:line` outcome or drop it, grade CRITICAL to LOW. Six finding categories, answers to the usual objections, a completion checklist, and a report with design fixes and a Reviewed/Not reviewed summary. Secret values are never quoted.
- Agent `sharp-edges-analyzer`: one interface per dispatch, at most five at once, Read/Grep/Glob only, replies with findings and one Reviewed/Not reviewed line.
- Reference catalogue in twelve files: crypto APIs, authentication and sessions, config schemas, Go, Python, JavaScript/TypeScript, Bash, native-library lessons, Ansible and YAML, Terraform, GitHub Actions (first CI section, five lead patterns) and GitLab CI.
- `tests/test_references.py`: reference links, entry shape, CI section order, code-block syntax, read-only tool lists.
- Evals: trigger, Go-plus-role outcome, GitHub Actions workflow outcome and a change-review negative; outcome cases forbid Write and Edit.
