---
name: module-creator
description: Creates and refactors Terraform modules whose interface is one YAML file (terraform.yml) — general_settings inheritance, def_/int_ naming, a four-stage locals pipeline, validate.tf checks and GitHub Actions CI — for OpenStack, VMware, AWS, Azure, GCP and Proxmox. Use when asked to create, write, refactor or update a Terraform module in that style. Not for providers — use terraform:provider-creator; not for running plan or apply on a root configuration.
argument-hint: "[module-name] [cloud=openstack|vmware|aws|azure|gcp|proxmox] [resource-type]"
effort: high
paths: ["**/modules/**/*.tf", "**/terraform.yml"]
allowed-tools: Bash(terraform fmt:*) Bash(terraform validate:*) Bash(terraform init -backend=false:*) Bash(tflint:*) Bash(terraform-docs:*) Bash(mkdir:*) Bash(date +%F) Read Write Edit Glob Grep
---

# Terraform module creator

Target: $ARGUMENTS (module name, cloud, main resource type; ask only for what is missing and
cannot be inferred from the repository).

The module's public interface is a YAML file, not a long list of variables. Consumers write
entities by name in `terraform.yml`; the module resolves defaults, validates, then creates
resources with `for_each`. Details live in the references; this file is the contract.

## Checklist

Copy and track:

```text
- [ ] Inspect the target: existing files, provider versions, state addresses (a refactor must keep them)
- [ ] Pin providers and the Terraform version in versions.tf
- [ ] Draft examples/terraform.yml first: it is the schema
- [ ] variables.tf, then locals.tf (four stages)
- [ ] Resource files, validate.tf with internal/validate_*, datasources.tf
- [ ] outputs.tf, examples/, README.md, CHANGELOG.md, .tflint.hcl
- [ ] CI workflow at the repository root (see File layout)
- [ ] Validation loop until every command exits 0
- [ ] Report: files written, command results, what was not validated and why
```

## Conventions

- One git repository per module, named `terraform-<system>-<name>`. Consumers pin by tag:
  `source = "git::https://github.com/<owner>/terraform-<system>-<name>.git?ref=vX.Y.Z"`.
  Examples inside the module use `source = "../"`.
- `versions.tf` sets `required_version = ">= 1.10.5"`. Every provider comes from the public
  registry with `version = "~> X.Y"` (pinned to the minor). Never invent a version: read it from
  the registry page or an existing module for the same system, or ask.
- Documentation is in English.

## Target clouds

Every cloud uses the entity map `virtual_machines`; the table gives the provider and the main
resource.

| Cloud | Provider source | Main resource |
|---|---|---|
| `openstack` | `terraform-provider-openstack/openstack` | `openstack_compute_instance_v2` |
| `vmware` | `hashicorp/vsphere` | `vsphere_virtual_machine` |
| `aws` | `hashicorp/aws` | `aws_instance` |
| `azure` | `hashicorp/azurerm` | `azurerm_linux_virtual_machine` |
| `gcp` | `hashicorp/google` | `google_compute_instance` |
| `proxmox` | `bpg/proxmox` | `proxmox_virtual_environment_vm` |

For `proxmox` read [references/PROXMOX.md](references/PROXMOX.md) before writing anything: it fixes
the schema keys, defaults and provider pitfalls.

## Configuration schema

`terraform.yml` has two kinds of top-level keys:

- `general_settings`: defaults applied to every entity.
- one or more entity maps: `virtual_machines`, plus further families (`volumes`, `cloud_init`,
  `containers`) when the target needs them.

```yaml
---
general_settings:
  flavor: m1.small
  image: debian-12
virtual_machines:
  web-01:
    flavor: m1.large
    disks:
      data: { size: 100 }
```

- Entities are name-keyed maps, never lists. The key is the `for_each` key. Nested families
  (`disks`) are name-keyed maps too.
- `immutable: true|false` picks between two resource variants with complementary filters; the
  mutable variant adds `lifecycle { ignore_changes }` for attributes that drift.
- Mutually exclusive pairs (`flavor`/`flavor_id`, `image`/`image_id`): a value of either member on
  the entity wins; the inherited member applies only when the entity sets neither; setting both
  on one entity is a validation error.

Inheritance, per parameter: the entity value, then the `general_settings` value, then the module
variable `def_<param>`. It is shallow: an entity that sets an object-valued key replaces the whole
inherited object, so document that per key in the README.

Variables that are always present:

- `config_file`: default `terraform.yml`; used as given, otherwise looked up under `path.root`; a
  `validation` block fails with a banner error when neither exists.
- `exclude_<entities>`: comma-separated names removed from the resolved entity map.
- `def_<param>`: only for parameters that have a sensible default.
- secrets: `sensitive = true`, default `null`, supplied by the consumer from a secret manager.

Names:

| Name | Holds |
|---|---|
| `var.def_<param>` | module-level default |
| `local.settings` | `general_settings` merged over the `def_*` values |
| `local.<entities>` (for example `local.vms`) | the resolved entity map |
| `local.int_<thing>` | internal derived structures (flattened disks, distinct image list) |
| `_dict`, `_list` suffix | map or list shape |

The locals pipeline has four stages, one `locals` block each, in order: load, settings,
entities, derived `int_*`. See [references/MODULE.md](references/MODULE.md).

## File layout

```text
terraform-<system>-<name>/
├── versions.tf  variables.tf  locals.tf  outputs.tf
├── <family>.tf                  # one file per resource family
├── datasources.tf               # every data source, only here
├── validate.tf
├── internal/validate_<entity>/  # vars_<entity>.tf, versions.tf, .tflint.hcl
├── examples/                    # main.tf, versions.tf, terraform.yml
├── README.md  CHANGELOG.md  .tflint.hcl
└── .github/workflows/ci.yml     # single-module repository only
```

GitHub reads workflows only from the repository root, so the CI workflow is never placed inside a
module directory.

- Single-module repository: `.github/workflows/ci.yml` at that root, from
  [templates/github-ci.yml](references/templates/github-ci.yml).
- Repository holding several modules (`modules/<system>/<name>/`): one
  `.github/workflows/ci.yml` at the repository root, from
  [templates/github-ci-monorepo.yml](references/templates/github-ci-monorepo.yml): a `paths`
  filter on `modules/**` and a matrix with one entry per module directory; each job runs with
  `working-directory: ${{ matrix.module }}`. When the root workflow already exists, add the new
  directory to its matrix instead of creating another file.
- The tag-triggered release job belongs to the single-module variant. In a monorepo tags are per
  repository; ask the user which scheme they want.

## Rules

- `for_each` only. Never `count`, including for optional resources: filter the map, or use a
  one-element map gated by a flag. Optional nested blocks use `dynamic` over `[]` or `[x]`.
- Logic lives in `locals.tf`; resource arguments reference finished values from `each.value`.
- Shared infrastructure (networks, zones, groups) comes in through inputs or `datasources.tf`;
  the module creates only what it owns.
- Every validation message has a banner of asterisks above and below, names the entity in angle
  brackets and states the fix. Validation runs before any data source or resource: they
  `depends_on` the entity's validate module.
- Secrets never appear in YAML, examples or defaults.
- Refactor with `moved` blocks for every renamed or re-keyed resource and keep old ones forever.
  A change that only `terraform state mv` could fix is a MAJOR bump.
- Null guards use a ternary: `x == null ? true : contains(list, x)`. Before Terraform 1.12 both
  operands of `||` and `&&` are evaluated, so `x == null || contains(list, x)` fails on null.

## Validation loop

Run in this order, repeating each until it exits 0:

1. `terraform fmt -recursive`
2. `terraform init -backend=false`
3. `terraform validate`
4. `tflint --init && tflint --recursive`
5. `terraform fmt -check -recursive`

Repeat init and validate inside `examples/`. When a `.pre-commit-config.yaml` exists, also run
pre-commit with `--files` listing every new file: new files are untracked and the default
staged-only run checks nothing. If init fails on registry or network access, report the exact
error and call the module "not validated"; never edit sources to get around it. More in
[references/VALIDATION.md](references/VALIDATION.md).

## Safety

- Never run `apply`, `destroy`, `import`, any `state` subcommand, or `plan` against real
  credentials. The user runs `plan` in `examples/`.
- Show a diff and ask before overwriting an existing file.
- Stop before commit, push, tag and release. Commits are signed off: `git commit -s`.

## Documentation

The README holds hand-written schema tables (the contract) plus a generated block between
`<!-- BEGIN_TF_DOCS -->` and `<!-- END_TF_DOCS -->`. Add the markers first, then run
`terraform-docs markdown table --output-file README.md --output-mode inject .`. Never use replace
mode on an existing README. Skeleton and sample in
[references/DOCUMENTATION.md](references/DOCUMENTATION.md); step-by-step creation and versioning
rules in [references/CREATION.md](references/CREATION.md).

## Related

- `terraform:provider-creator` for providers.
- Agent `terraform:terraform-engineer` for state layout, module boundaries and plan review.
