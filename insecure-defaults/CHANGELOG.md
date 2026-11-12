# Changelog

## 2026-11-11

### Added

- Skill `audit`: static, read-only audit for insecure defaults in six categories (secrets with literal fallbacks, shipped credentials, checks that fail open, broken or misused crypto, over-broad access, debug surfaces left on) across Go, Python, Bash, TypeScript/JavaScript, Terraform, Ansible and GitHub Actions workflows. Four phases (recon, discover, verify, report); a missing target path aborts; every seed runs as its own POSIX ERE `grep -rnE`; candidates are refuted unless a five-step trace finds a security sink and a deployment that runs the value; the report always carries coverage and limits, "worth a manual check" commands and a refuted table. Secret values are never printed.
- GitHub Actions scope: `pull_request_target` and `workflow_run` with PR checkout, missing or broad `permissions:`, actions not pinned to a commit SHA, `${{ github.event.* }}` in `run:`, `continue-on-error` on gates, `secrets: inherit`, runner debug flags and secret echoes. Workflows also count as deploy manifests.
- Agent `default-verifier`: read-only verifier for batches of up to 16 candidates on large targets, at most five at once; returns one verdict block per candidate and writes nothing.
- Reference corpus: per category a seed file (68 seeds in total) and an examples file with vulnerable and secure cases, including Go, Bash, HCL, Ansible and workflow examples.
- `tests/test_corpus.py`: checks the skill's category table against the corpus files, seed hygiene (no `\s`, `\d`, `\b`), corpus shape, that every vulnerable example is matched by a seed and every seed matches an example, and stack coverage.
- Evals: trigger, outcome and negative cases, including Go, Ansible, Ansible plus Terraform, and GitHub Actions outcomes that forbid edits and any run of the target's tooling.
