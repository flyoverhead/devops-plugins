# Proxmox VE target

## Contents

- Provider and prerequisites
- File structure
- terraform.yml schema
- Defaults and the locals pipeline
- The VM resource
- Cloud-init snippets
- Validation
- Outputs
- Pitfalls

## Provider and prerequisites

Provider `bpg/proxmox`, pinned to `~> 0.111.0`; check the registry before bumping:

```hcl
terraform {
  required_version = ">= 1.10.5"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.111.0"
    }
  }
}
```

- The module contains no `provider` block and no data sources: the caller configures
  the provider (endpoint, API token, and an `ssh` block when snippets are used), so a plan
  never reaches the API from inside the module. Put cluster discovery (nodes, datastores,
  free guest ids) in a separate read-only example, not in the module.
- The API token needs privilege separation disabled, or an explicit ACL for pools, VMs
  and file upload. A privilege-separated token without an ACL does not error; it returns
  empty results, which looks like a wrong endpoint.
- Proxmox VE 8.x and 9.x; 7.x is unsupported.

## File structure

```
terraform-proxmox-<name>/
├── versions.tf  variables.tf  locals.tf  outputs.tf
├── vms.tf               # proxmox_virtual_environment_vm.this, for_each = local.vms
├── pool.tf              # optional proxmox_virtual_environment_pool
├── cloud_init.tf        # optional proxmox_virtual_environment_file snippets
├── validate.tf  internal/validate_settings/  internal/validate_vms/
├── examples/{main.tf,versions.tf,terraform.yml,templates/cloud-config.yaml.tftpl}
├── README.md  CHANGELOG.md  .tflint.hcl  .github/workflows/ci.yml
```

Containers (`proxmox_virtual_environment_container`) follow the same pattern in
`containers.tf` with their own entity map `containers`; add them only when asked. Guests
of both types share one `vm_id` space and one name space, so cross-entity validation runs
over the merged set.

## terraform.yml schema

```yaml
---
general_settings:
  node: pve-01
  pool: managed
  datastore: local-lvm
  snippet_datastore: local        # needs the snippets content type enabled
  bridge: vmbr0
  tags: [terraform]
  template_id: 9000               # VMs are clones of a template
  cores: 2
  memory: 2048                    # MiB
  disk_size: 20                   # GiB; omit to keep the template disk
  agent: false                    # see Pitfalls
  username: ops
  ssh_keys: []
  nameservers: [10.0.0.1]
  searchdomain: example.internal

cloud_init:                       # optional snippets, keyed by name
  base:
    template: templates/cloud-config.yaml.tftpl
    vars:
      packages: [curl]

virtual_machines:
  web-01:
    vm_id: 9901                   # optional; omit to let Proxmox assign
    cores: 4
    memory: 8192
    ipv4: { address: 10.0.10.11/24, gateway: 10.0.10.1 }
    cloud_init: base
    tags: [web]
  db-01:
    template_id: 9001
    disk_size: 100
    ipv4: { address: dhcp }
```

`merge`-style inheritance is shallow: an entity that sets `ipv4` replaces the whole object
from `general_settings`. Set the whole object wherever any part of it is set, and say so
in the README.

## Defaults and the locals pipeline

Follow the four stages in MODULE.md. Variables: `config_file`, `def_cores`
(2), `def_memory` (2048), `def_disk_size` (`null`), `def_cpu_type` (`x86-64-v2-AES`),
`def_bridge` (`vmbr0`, validated against `^vmbr[0-9]+$`), `exclude_vms`.

- Every key a resource reads must exist in the resolved entity (default `null`, or `[]` for list keys), so
  resource arguments never hit a missing attribute. Explicit non-null defaults:
  `disk_interface: scsi0` (the provider requires `disk.interface`), `nameservers: []`,
  `ssh_keys: []`, `tags: []`; `length(null)` fails in the dynamic-block guards.
- `tags` are sorted in the entity stage: Proxmox returns tags sorted, so an unsorted list
  plans a diff that no apply converges.
- `agent` defaults to `false` and has no `def_` variable.
- `disk_size` defaults to `null`, never a number.

## The VM resource

```hcl
resource "proxmox_virtual_environment_vm" "this" {
  for_each = local.vms

  name            = each.key
  node_name       = each.value.node
  vm_id           = each.value.vm_id
  pool_id         = each.value.pool
  tags            = each.value.tags
  description     = each.value.description
  stop_on_destroy = each.value.stop_on_destroy

  clone {
    vm_id = each.value.template_id
    full  = true
  }

  agent {
    enabled = each.value.agent
  }

  cpu {
    cores = each.value.cores
    type  = each.value.cpu_type
  }

  memory {
    dedicated = each.value.memory
  }

  dynamic "disk" {
    for_each = each.value.disk_size == null ? [] : [each.value.disk_size]

    content {
      datastore_id = each.value.datastore
      interface    = each.value.disk_interface
      size         = disk.value
    }
  }

  initialization {
    datastore_id = each.value.datastore

    dynamic "dns" {
      for_each = length(each.value.nameservers) > 0 || each.value.searchdomain != null ? [1] : []

      content {
        servers = each.value.nameservers
        domain  = each.value.searchdomain
      }
    }

    dynamic "ip_config" {
      for_each = each.value.ipv4 == null ? [] : [each.value.ipv4]

      content {
        ipv4 {
          address = ip_config.value.address
          gateway = try(ip_config.value.gateway, null)
        }
      }
    }

    dynamic "user_account" {
      for_each = each.value.username == null && length(each.value.ssh_keys) == 0 ? [] : [1]

      content {
        username = each.value.username
        keys     = each.value.ssh_keys
      }
    }

    user_data_file_id = (
      each.value.cloud_init == null
      ? null
      : proxmox_virtual_environment_file.cloud_init[each.value.cloud_init].id
    )
  }

  network_device {
    bridge = each.value.bridge
  }

  depends_on = [module.validate_vms]
}
```

Optional pool: `for_each = local.settings.pool == null ? {} : { this = local.settings.pool }`,
and read it back as `try(proxmox_virtual_environment_pool.this["this"].pool_id, null)`.

## Cloud-init snippets

```hcl
resource "proxmox_virtual_environment_file" "cloud_init" {
  for_each = local.cloud_init

  content_type = "snippets"
  datastore_id = local.settings.snippet_datastore
  node_name    = local.settings.node

  source_raw {
    file_name = "${each.key}-cloud-config.yaml"
    data      = templatefile("${path.root}/${each.value.template}", try(each.value.vars, {}))
  }
}
```

- Upload goes over SSH, not the API. The caller's provider needs an `ssh` block, and with
  API token auth `ssh.username` is mandatory. Without SSH, use the inline
  `username` + `ssh_keys` + `ipv4` path instead.
- The file name comes from the map key, so identical content never drifts.
- Snippets are uploaded to `general_settings.node` only: a VM referencing one must resolve
  the same node, unless the snippet datastore is shared storage (the module cannot tell).
- Template paths resolve against `path.root`.

## Validation

`validate.tf` calls `internal/validate_settings` (bridge pattern, required `node`) and
`internal/validate_vms`, which receives the whole resolved `local.vms` map so it can
compare entities with each other. Checks, each with the banner error format naming the
entity:

| Check | Why |
|---|---|
| `template_id` resolved on every VM | VMs are clones; no template means no VM |
| assigned `vm_id` is 100 or higher (the provider rejects lower ids) and unique | Proxmox does not reject a second claim cleanly |
| static `ipv4.address` values are unique | Proxmox accepts duplicates; guests then fight on the network |
| a static address has a CIDR suffix and a gateway | a bare address misconfigures the guest silently |
| `cloud_init` names an existing `cloud_init` key | otherwise the file id is null |
| a VM with `cloud_init` resolves the snippet node | snippets live on one node |
| resolved `bridge` matches `^vmbr[0-9]+$` | values set in `general_settings` or on an entity bypass `def_bridge` validation |

Do not pattern-check `node`, `datastore`, `disk_interface` or `cpu_type`: they are
cluster-specific strings and the provider reports bad ones.

## Outputs

`virtual_machines`: map of name to `vm_id`, `name`, `node_name`, `ipv4_addresses`;
`pool_id`; `cloud_init_file_ids`. Add `resolved_virtual_machines = local.vms` so callers
and `terraform test` can inspect the settings a guest resolved to.
`ipv4_addresses` comes from the guest agent only; it is empty when the agent is off.

## Pitfalls

| Pitfall | Rule |
|---|---|
| `agent = true` on a template without a running qemu-guest-agent | The provider waits its full 15-minute timeout for addresses with no error. Default `false`; set `true` only when the template runs the agent |
| A `disk` block on a clone | It resizes the inherited disk and can add a second one. Emit it only when `disk_size` is set, and never below the template size: Proxmox cannot shrink disks |
| An empty `dns` block (`servers = []`) | Proxmox stores nothing, so the next refresh reads no block and the diff never converges. Emit `dns` only when there is something to set |
| `user_account` gated on `username` alone | Drops `ssh_keys` silently. Emit it when either is set; `username` is optional in the provider schema |
| Unsorted `tags` | Sort in `locals.tf` |
| Containers and `username` | `initialization.user_account` on a container has only `keys` and `password`; keys land on `root` |
| Containers and `cloud_init` | Snippets are VM user-data with no container equivalent; reject it on a container |
