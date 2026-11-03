# Module code patterns

Patterns for the YAML-driven module style. The examples describe an imaginary block-storage
module with a `volumes` entity map; adapt names to the target.

## Contents

- variables.tf
- The four-stage locals pipeline
- for_each shapes
- Validation layers
- File-path inputs
- Anti-patterns

## variables.tf

The file stays thin. It holds the config file path, module-level defaults, the exclude list and
secrets, and nothing per entity field: entity fields live in the YAML.

```hcl
variable "config_file" {
  description = "Path to the YAML configuration, as given or relative to the root module"
  type        = string
  default     = "terraform.yml"

  validation {
    condition     = fileexists(var.config_file) || fileexists("${path.root}/${var.config_file}")
    error_message = <<-EOT
      ************************************************************
      Config file <${var.config_file}> was not found.
      Pass an existing path, or place the file in the root module.
      ************************************************************
    EOT
  }
}

variable "def_size" {
  description = "Default volume size in GiB"
  type        = number
  default     = 10
}

variable "def_tier" {
  description = "Default volume type"
  type        = string
  default     = "standard"
}

variable "exclude_volumes" {
  description = "Comma-separated volume names to leave out"
  type        = string
  default     = ""
}

variable "encryption_passphrase" {
  description = "Passphrase for encrypted volumes, supplied from a secret manager"
  type        = string
  default     = null
  sensitive   = true
}
```

## The four-stage locals pipeline

Four `locals` blocks, always in this order. A later stage reads only earlier stages.

| Stage | Block purpose | Output |
|---|---|---|
| 1 load | resolve the file path, decode YAML, cut out sections, parse the exclude list | `config`, `general_settings`, `<entities>_cfg`, `excluded` |
| 2 settings | `general_settings` over `def_*` | `settings` |
| 3 entities | entity over settings, computed fields, exclusion filter | `<entities>` |
| 4 derived | flattened and distinct structures for resources and data sources | `int_*` |

Stage 1. Choose the string before decoding. Choosing between two decoded values of different
shapes fails at plan time with a type mismatch.

```hcl
locals {
  config_path = fileexists(var.config_file) ? var.config_file : "${path.root}/${var.config_file}"
  config      = yamldecode(fileexists(local.config_path) ? file(local.config_path) : "{}")

  general_settings = try(local.config.general_settings, {})
  volumes_cfg      = try(local.config.volumes, {})
  excluded         = compact([for n in split(",", var.exclude_volumes) : trimspace(n)])
}
```

Stage 2. A parameter that has a default uses `coalesce` with the `def_` variable. A nullable
parameter uses `try` alone. Never `coalesce` over a chain that can be entirely null: it raises an
error instead of returning null.

```hcl
locals {
  settings = {
    size              = coalesce(try(local.general_settings.size, null), var.def_size)
    tier              = coalesce(try(local.general_settings.tier, null), var.def_tier)
    availability_zone = try(local.general_settings.availability_zone, null)
  }
}
```

Stage 3. Entity values come from `try(entity.x, settings.x)`. Exclusion is a trailing `if`.
Computed fields (a name from key plus domain, a resolved pair) are built here, not in the
resource. Every key a resource reads exists on every entity, with `null` or an empty collection as
the fallback.

```hcl
locals {
  volumes = {
    for name, v in local.volumes_cfg : name => {
      name              = name
      size              = try(v.size, local.settings.size)
      tier              = try(v.tier, local.settings.tier)
      availability_zone = try(v.availability_zone, local.settings.availability_zone)
      encrypted         = try(v.encrypted, false)
      snapshots         = try(v.snapshots, {})
    } if !contains(local.excluded, name)
  }
}
```

Stage 4. Flatten nested families into one map with the composite key `<parent>_<child>`; build
distinct lists for data source lookups (`int_uniq_*_list`).

```hcl
locals {
  int_snapshots = merge([
    for vname, v in local.volumes : {
      for sname, s in v.snapshots : "${vname}_${sname}" => {
        volume = vname
        name   = sname
        note   = try(s.note, null)
      }
    }
  ]...)

  int_uniq_tier_list = distinct([for v in local.volumes : v.tier])
}
```

Lookups: `try()` covers one level at a time. For `a.b.c.d` go through intermediates
(`b = try(a.b, {})`, then `try(b.c, null)`), because a `try` over a long chain hides which part
was wrong.

## for_each shapes

```hcl
resource "example_volume" "this" {
  for_each = local.volumes
}

resource "example_volume_encryption" "this" {
  for_each = { for k, v in local.volumes : k => v if v.encrypted }
}

data "example_tier" "this" {
  for_each = toset(local.int_uniq_tier_list)
}

resource "example_volume_attachment" "this" {
  for_each = local.volumes

  dynamic "limits" {
    for_each = each.value.size > 100 ? [each.value.size] : []
    content {
      iops = limits.value * 10
    }
  }
}
```

Whole map, filtered map, `toset` of a distinct list, and `dynamic` over `[]` or a one-element
list. Never `count`.

## Validation layers

1. Variable-level `validation`: cheap checks on one variable (the config file exists). A
   validation may refer to other variables and locals; this needs Terraform 1.9 or later, which
   the 1.10.5 floor satisfies.
2. `validate.tf` calls `./internal/validate_settings`, then `./internal/validate_<entity>` with
   `for_each` over the entity map, passing the name and the resolved object. The internal modules
   hold variables with `validation` blocks and nothing else: no resources, no data sources.
3. Resources and data sources `depends_on` those modules, so a bad config stops at the banner
   message and never reaches a provider.
4. `precondition` blocks only where provider data is needed for the check.

**`validate.tf`**

```hcl
module "validate_settings" {
  source   = "./internal/validate_settings"
  settings = local.settings
}

module "validate_volumes" {
  source   = "./internal/validate_volumes"
  for_each = local.volumes

  name       = each.key
  volume     = each.value
  depends_on = [module.validate_settings]
}
```

**`internal/validate_volumes/vars_volumes.tf`**

```hcl
variable "name" {
  type = string
}

variable "volume" {
  type = any

  validation {
    condition     = var.volume.size >= 1 && var.volume.size <= 16384
    error_message = <<-EOT
      ************************************************************
      Volume <${var.name}>: size ${var.volume.size} is outside 1..16384 GiB.
      Set 'size' for this volume, or fix general_settings.size.
      ************************************************************
    EOT
  }

  validation {
    condition     = var.volume.encrypted ? var.volume.tier != "standard" : true
    error_message = <<-EOT
      ************************************************************
      Volume <${var.name}>: encryption needs a tier other than 'standard'.
      Change 'tier' or set 'encrypted: false'.
      ************************************************************
    EOT
  }
}
```

When a check compares entities with each other (unique ids, unique addresses), call the internal
module once and pass the whole resolved map instead of using `for_each`.

The internal directory also needs a `versions.tf` and a `.tflint.hcl` that disables
`terraform_unused_declarations` (the variables there are read only by validation).

## File-path inputs

A path in the YAML (a template file, a certificate) resolves as given, then under `path.root`,
else `null`. Validation rejects a path that is set but resolves to nothing.

```hcl
locals {
  template_path = try(local.settings.template, null)
  template_resolved = (
    local.template_path == null ? null
    : fileexists(local.template_path) ? local.template_path
    : fileexists("${path.root}/${local.template_path}") ? "${path.root}/${local.template_path}"
    : null
  )
}
```

## Anti-patterns

| Avoid | Instead |
|---|---|
| A wrapper module around one resource | Put the resource in the module that owns the lifecycle, or use it directly |
| A long variable list that repeats the schema | One YAML file plus `config_file` |
| Entities as a list | Name-keyed map; the key is the `for_each` key |
| `count` | `for_each` over a filtered map |
| Inline conditionals in resource arguments | Resolve the value in stage 3, reference `each.value.x` |
| Creating networks, zones or groups the module only uses | Accept them as input or read them in `datasources.tf` |
| Modules nested several levels deep | Flat root plus `internal/validate_*` |
| Provider `version` left floating | `~>` pin to the minor in `versions.tf` |
| Secrets in YAML, examples or defaults | `sensitive` variable, default `null`, value from a secret manager |
