# terraform

YAML-driven Terraform modules and Plugin Framework providers, with terraform-ls and safety hooks.

```text
/plugin install terraform@devops
```

## Skills

| Skill | Use it for |
|---|---|
| `module-creator` | Modules driven by `terraform.yml` for OpenStack, VMware, AWS, Azure, GCP and Proxmox, with GitHub Actions CI at the repository root (single module or a matrix over `modules/**`) |
| `provider-creator` | Go providers on the Plugin Framework with in-process acceptance tests and a GPG-signed GitHub Actions release to the Terraform Registry |

## Agent

`terraform-engineer`: state layout, root configuration structure, module boundaries and plan
review across several modules or states.

## Hooks

| Event | Behaviour |
|---|---|
| After `Edit` or `Write` of `.tf` and `.tfvars` | runs `terraform fmt` on that file |
| After `Edit` or `Write` of `.tf` | runs `terraform validate` when the module is initialised and reports failures to Claude |
| Session start | reports the installed Terraform version as additional context |
| Before `Bash` | blocks `apply`, `destroy`, `import`, `taint`, `untaint`, `force-unlock`, `refresh`, `workspace delete` and the state-mutating `state mv`, `state rm`, `state push` and `state replace-provider` |

The guard also catches these commands behind `-chdir=`, behind wrappers such as `sudo`, `env`,
`timeout`, `nice`, `nohup` and `xargs`, inside `bash -c`, subshells and command substitution, and
for `tofu`. `plan`, `validate`, `fmt`, `init`, `output`, `show`, `test`, `state list`,
`state show` and `state pull` stay allowed. Without `jq`, or without `python3` once a
command mentions `terraform` or `tofu`, the guard prints a warning to stderr and lets every
command through.

## Required tools

- `terraform` (or `tofu` for the guard's purposes)
- optional: `terraform-ls`, `tflint`, `terraform-docs`; `jq` and `python3` for the guard
- for providers: `go`, `golangci-lint`, `actionlint`, `goreleaser`
