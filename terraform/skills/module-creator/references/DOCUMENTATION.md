# Module documentation

## Contents

- README skeleton
- terraform-docs injection
- CHANGELOG
- Sample README

## README skeleton

1. Title and a one-line summary.
2. A note that the module follows semantic versioning.
3. Usage: a `module` block with a git source pinned to a tag (`<owner>` stands for the account
   that hosts the repository).
4. Environment variables the provider reads, as a table.
5. Schema: one table for `general_settings` and one per entity map, with the columns key,
   required, type, default, inherits from, meaning.
6. An example `terraform.yml`.
7. A short summary of the outputs.
8. The generated block between `<!-- BEGIN_TF_DOCS -->` and `<!-- END_TF_DOCS -->`.

Hand-written tables are the contract: the generated block lists variables and outputs but cannot
describe the YAML. For every object-valued key, say that inheritance is shallow and an entity value
replaces the whole inherited object.

## terraform-docs injection

```bash
terraform-docs markdown table --output-file README.md --output-mode inject .
```

Add the two marker lines to the README first. Without markers, `inject` appends the block at the
end of the file. `replace` mode rewrites the whole file and discards the hand-written tables, so it
is never used on an existing README.

## CHANGELOG

Keep-a-Changelog layout. Each release heading carries a version and an ISO date. Entries sit under
Added, Changed or Fixed. A breaking item is labelled **BREAKING** and shown with before and after
YAML so a consumer can migrate.

```markdown
## [2.0.0] - 2026-11-03

### Changed

- **BREAKING**: `ttl` is now `ttl_seconds`.

  Before:

  ~~~yaml
  records:
    api: { ttl: 300 }
  ~~~

  After:

  ~~~yaml
  records:
    api: { ttl_seconds: 300 }
  ~~~
```

## Sample README

A DNS record module, to show the shape; use the real entity for the module at hand.

````markdown
# terraform-example-dns

Creates DNS records in a zone from a YAML file.

The module follows [semantic versioning](https://semver.org). Pin a tag.

## Usage

```hcl
module "dns" {
  source      = "git::https://github.com/<owner>/terraform-example-dns.git?ref=v1.0.0"
  config_file = "${path.module}/terraform.yml"
}
```

## Environment variables

| Variable | Used by | Meaning |
|---|---|---|
| `EXAMPLE_API_TOKEN` | provider | API token with write access to the zone |

## Configuration

### `general_settings`

| Key | Required | Type | Default | Inherits from | Meaning |
|---|---|---|---|---|---|
| `zone` | yes | string | none | none | Zone that receives every record |
| `ttl` | no | number | `def_ttl` (300) | `def_ttl` | Record lifetime in seconds |

### `records`

| Key | Required | Type | Default | Inherits from | Meaning |
|---|---|---|---|---|---|
| `type` | no | string | `A` | none | Record type |
| `values` | yes | list(string) | none | none | Record data |
| `ttl` | no | number | settings value | `general_settings.ttl` | Overrides the inherited lifetime |

### Example

```yaml
---
general_settings:
  zone: example.internal.
records:
  api:
    values: [10.0.0.10]
  mail:
    type: MX
    values: ["10 mx.example.internal."]
    ttl: 3600
```

## Outputs

`records` maps each record name to its fully qualified name and ttl.

<!-- BEGIN_TF_DOCS -->
<!-- END_TF_DOCS -->
````
