# Module validation

## Contents

- The loop
- CI
- What the user verifies
- Review checklist
- Common failures

## The loop

Run from the module root, in this order. Repeat each command until it exits 0.

```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate
tflint --init && tflint --recursive
terraform-docs markdown table --output-file README.md --output-mode inject .
terraform fmt -check -recursive
```

Then repeat `init -backend=false` and `validate` inside `examples/`.

- tflint runs per directory with that directory's `.tflint.hcl`. The `internal/validate_*`
  directories use the internal preset, which disables `terraform_unused_declarations` because their
  variables are read only by `validation` blocks.
- terraform-docs needs the `<!-- BEGIN_TF_DOCS -->` markers in the README before the first run.
- With a `.pre-commit-config.yaml`, run pre-commit with `--files` and every new file: new files are
  untracked and a staged-only run checks nothing.
- If `init` cannot reach the registry, report the exact error, mark the module "not validated" and
  stop. Do not rewrite sources to avoid the download.
- When the module has a `tests/` directory, `terraform test` runs it. Tests use
  `mock_provider` and `command = plan` against a fixture YAML, so they need no credentials: assert
  on `resolved_<entities>` for inheritance and exclusion, and use `expect_failures` for rejected
  input. The fixture's file paths are relative to the module root, where the test runs.
- No tfsec, checkov or trivy step is added to the module.

## CI

The workflow lives at the repository root: GitHub ignores workflow files anywhere else. A
single-module repository uses `templates/github-ci.yml`; a repository with several modules uses
`templates/github-ci-monorepo.yml`, whose matrix has one entry per module directory.

| Step | Fails when |
|---|---|
| `terraform fmt -check -recursive` | any file is unformatted |
| init and validate, module and `examples/` | configuration is invalid |
| tflint | a rule fires |
| terraform-docs inject with diff check | the generated README block is stale |
| release (`v*` tag, single-module workflow only) | the tag does not exist; creates the GitHub release |

## What the user verifies

The assistant never applies or destroys. The user runs, with real credentials:

```bash
cd examples && terraform init && terraform plan
```

and reads the plan: a plan describes intended changes to real infrastructure, so it is read before
anything applies it. For a refactor the expected result is no changes, or moves only.

## Review checklist

- [ ] one validate module per entity, and every dependent resource and data source depends on it
- [ ] no `count` anywhere
- [ ] data sources only in `datasources.tf`
- [ ] providers from the public registry, pinned with `~>` to the minor
- [ ] secrets are `sensitive` variables with default `null`
- [ ] every YAML key is documented with its inheritance
- [ ] every rename or re-key has a `moved` block
- [ ] the CHANGELOG entry matches the bump rule
- [ ] the workflow is at the repository root, not in a module directory

## Common failures

| Symptom | Cause and fix |
|---|---|
| Banner says the config file was not found, though the file exists | The path is relative to the wrong directory. Pass it as `"${path.module}/terraform.yml"`, or place it in the root module |
| `The "for_each" map includes keys derived from resource attributes that cannot be determined until apply` | A key comes from a resource attribute. Key by the input name |
| `no non-null, non-empty-string arguments` from `coalesce` | Every argument was null. Use `try(...)` alone for nullable parameters, and give `def_` variables a real default |
| `each.value` or a comprehension variable is "not defined" in a resource | Resource bodies use `each.key` and `each.value`; the comprehension variable exists only inside `locals.tf` |
| Plan wants to replace resources after a refactor | A `moved` block is missing, or the key format changed. Add the block, or declare it a MAJOR change |
| A provider error appears instead of the banner message | The resource or data source lacks `depends_on = [module.validate_<entity>]` |
| `x == null \|\| contains(list, x)` errors on null | Before Terraform 1.12 both operands are evaluated. Write `x == null ? true : contains(list, x)` |
