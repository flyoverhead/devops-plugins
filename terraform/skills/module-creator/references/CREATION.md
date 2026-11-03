# Creating and changing a module

Order of work, file by file, plus the versioning rules. Code style is in `MODULE.md`;
verification is in `VALIDATION.md`.

## Contents

- Order of work
- versions.tf
- Resources
- Data sources
- Outputs
- Examples
- Refactoring with moved blocks
- Versioning
- CI placement

## Order of work

1. `examples/terraform.yml`: the schema, written as a consumer would use it.
2. `versions.tf`, `variables.tf`, `locals.tf`.
3. `validate.tf` and `internal/validate_*`.
4. `datasources.tf` and one file per resource family.
5. `outputs.tf`, `examples/main.tf`, `examples/versions.tf`.
6. `README.md`, `CHANGELOG.md`, `.tflint.hcl` from `templates/tflint.hcl`. Each
   `internal/validate_*` directory gets its own `versions.tf` and the file
   `templates/tflint-internal.hcl` copied as its `.tflint.hcl`.
7. The CI workflow, placed as described under CI placement.

For a refactor, read the existing resources first and list their addresses; every address that
changes needs a `moved` block.

## versions.tf

```hcl
terraform {
  required_version = ">= 1.10.5"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.0"
    }
  }
}
```

The provider version is read from the registry or from a sibling module, not from memory. Only
public-registry sources: never a `registry.` hostname in `source`. Modules declare no `provider`
blocks; the caller configures them.

## Resources

- Name a resource by its role (`this`, `data`, `boot`), not by repeating the type.
- The body uses `each.key` and `each.value`. Comprehension variables from `locals.tf` do not exist
  here.
- Every resource that must wait for validation has `depends_on = [module.validate_<entity>]`.
- An attachment or association resource gets its own filtered `for_each`, keyed like the thing it
  attaches (`<vm>_<disk>`), built in stage 4.

The immutable flag is two resource blocks with complementary filters. The mutable one ignores the
attributes that change outside Terraform:

```hcl
resource "openstack_compute_instance_v2" "immutable" {
  for_each = { for k, v in local.vms : k => v if v.immutable }

  name        = each.key
  flavor_name = each.value.flavor
  image_name  = each.value.image
  key_pair    = each.value.key_pair

  depends_on = [module.validate_vms]
}

resource "openstack_compute_instance_v2" "mutable" {
  for_each = { for k, v in local.vms : k => v if !v.immutable }

  name        = each.key
  flavor_name = each.value.flavor
  image_name  = each.value.image
  key_pair    = each.value.key_pair

  lifecycle {
    ignore_changes = [flavor_name, image_name, key_pair]
  }

  depends_on = [module.validate_vms]
}
```

Code that needs an instance of either variant reads a merged map. Stage 4 only reads input
values, so build that map in a small `locals` block placed next to the consumer, after the
resources:

```hcl
locals {
  instances = merge(
    openstack_compute_instance_v2.immutable,
    openstack_compute_instance_v2.mutable,
  )
}
```

An optional resource is an empty map when absent, so nothing is created. A single optional
resource is read back with `one(values(...))`, or `try(r["this"].attr, null)` for a fixed key.
There is no `[0]` because there is no `count`.

```hcl
resource "openstack_networking_secgroup_v2" "this" {
  for_each = local.settings.create_secgroup ? { this = "${var.name_prefix}-sg" } : {}

  name = each.value
}

output "secgroup_id" {
  value = try(openstack_networking_secgroup_v2.this["this"].id, null)
}
```

Attachments:

```hcl
resource "openstack_compute_volume_attach_v2" "this" {
  for_each = local.int_disks

  instance_id = local.instances[each.value.vm].id
  volume_id   = openstack_blockstorage_volume_v3.this[each.key].id
}
```

## Data sources

Data sources live in `datasources.tf` only, one per distinct value, driven by the `int_uniq_*`
lists from stage 4. They `depends_on` the validate modules so a bad value fails with the banner
message, not with a provider "not found".

```hcl
data "openstack_images_image_v2" "this" {
  for_each = toset(local.int_uniq_image_list)

  name        = each.key
  most_recent = true

  depends_on = [module.validate_settings, module.validate_vms]
}
```

## Outputs

- A detailed per-entity map keyed like the input (`virtual_machines`).
- Narrow outputs for downstream consumers (`vm_ids`, `fixed_ips`).
- `resolved_<entities> = local.<entities>` only when it helps tests and debugging.

Mark an output `sensitive` when it carries credentials.

## Examples

`examples/` is a runnable root configuration:

- `main.tf`: one `module` block with `source = "../"` and
  `config_file = "${path.module}/terraform.yml"`.
- `versions.tf`: the same `required_version` and providers, plus provider configuration with
  placeholder endpoints.
- `terraform.yml`: uses every schema key at least once, so a reader sees the whole contract.

## Refactoring with moved blocks

Every renamed or re-keyed resource gets a `moved` block, kept forever:

```hcl
moved {
  from = openstack_compute_instance_v2.this
  to   = openstack_compute_instance_v2.mutable
}
```

A re-key (from `name` to `name_disk`) needs a block for each instance key when the key set is
small; for large sets move to a new resource name via a one-time `terraform state mv` run by the
user and call it out as a MAJOR change. `moved` handles rename and re-key only; it cannot split or
merge resources.

## Versioning

| Bump | Triggers |
|---|---|
| MAJOR | key renamed or removed; a changed default that touches existing resources; output removed; anything that plans a replace or destroy for unchanged YAML |
| MINOR | new optional key; new entity type; new output; validation stricter but still accepting every previously valid config |
| PATCH | fix with identical plans; documentation |

The CHANGELOG entry must match the bump. The user creates the tag; the assistant does not.

## CI placement

GitHub reads workflows only from the repository root.

- A repository with one module: `.github/workflows/ci.yml` at the root, from
  `templates/github-ci.yml` (format, init and validate of module and `examples/`, tflint, docs
  check, and a release job for `v*` tags).
- A repository with several modules under `modules/<system>/<name>/`: one root
  `.github/workflows/ci.yml`, from `templates/github-ci-monorepo.yml`. It triggers on a `paths`
  filter for `modules/**` and runs a matrix with one entry per module directory; each step uses
  `working-directory: ${{ matrix.module }}`. Adding a module means adding its directory to the
  matrix. There is no release job: tags are per repository, so the user chooses the scheme.
- Never write a workflow inside a module directory.
