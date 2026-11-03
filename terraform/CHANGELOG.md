# Changelog

## 2026-11-03

Initial release.

- `module-creator` skill: YAML-driven modules for OpenStack, VMware, AWS, Azure, GCP and Proxmox
  with `general_settings` inheritance, a four-stage locals pipeline, banner-style validation modules
  and moved-block refactoring. The CI workflow is written at the repository root: the single-module
  template, or a monorepo template with a `paths` filter and a matrix over module directories.
- `provider-creator` skill: Plugin Framework provider scaffold with an API client package,
  in-process fake API acceptance tests, goreleaser configuration and a GPG-signed GitHub Actions
  release. The test workflow covers the two latest Terraform minor releases.
- `terraform-engineer` agent for state layout, module boundaries and plan review.
- Hooks: format on edit, validate for initialised modules, version report at session
  start, and a Bash guard that blocks `apply`, `destroy`, `import`, `taint`, `untaint`,
  `force-unlock`, `refresh`, `workspace delete`, `state mv`, `state rm`, `state push` and
  `state replace-provider`, including behind `-chdir=`, common wrappers, `bash -c`, subshells and
  `tofu`.
- terraform-ls language server configuration.
- Eval suite covering skill triggers, negative cases and outcome checks.
