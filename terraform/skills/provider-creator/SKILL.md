---
name: provider-creator
description: Creates Terraform providers in Go on the Plugin Framework — scaffold, API client, resources, data sources, acceptance tests against an in-process fake API, and a GPG-signed GitHub Actions release to the Terraform Registry. Use when asked to create or scaffold a Terraform provider, wrap an HTTP API as a provider, add a resource or data source to an existing provider, or migrate a provider from SDKv2 to the Plugin Framework. Not for modules — use terraform:module-creator.
argument-hint: "[provider-name] [api-base-url]"
effort: high
allowed-tools: Bash(go build:*) Bash(go vet:*) Bash(go test:*) Bash(go mod:*) Bash(go list:*) Bash(gofmt:*) Bash(golangci-lint run:*) Bash(actionlint:*) Bash(terraform fmt:*) Bash(terraform validate:*) Bash(go tool tfplugindocs:*) Bash(mkdir:*) Read Write Edit Glob Grep
---

# Terraform provider creator

Target: $ARGUMENTS (provider name and API base URL).

Scaffolds a first-party provider laid out like `terraform-provider-scaffolding-framework`,
released by GitHub Actions with goreleaser and GPG-signed checksums to the public Terraform
Registry.

## Checklist

Copy and track:

```text
- [ ] Choose the archetype (below)
- [ ] Collect inputs: provider name, API base URL, owner, resources to model
- [ ] go.mod first; resolve dependency versions from the module proxy
- [ ] main.go, internal/client, internal/provider, examples/
- [ ] Copy the config assets (table below)
- [ ] Tests: client unit tests, acceptance tests against the fake API
- [ ] Validation loop until every command is clean
- [ ] Report: files, command results, assumptions, what was not run
```

## Archetype

| Situation | Action |
|---|---|
| An upstream provider exists and is used unchanged | Nothing to build: tell the user to use it and stop |
| An upstream provider needs changes | Keep its SDK and layout; carry changes as patch files; no migration |
| No provider exists for the API | This skill |

## Inputs

Required: provider name and API base URL. When both are given, proceed assuming bearer-token
authentication and standard collection CRUD for the resources named; list those assumptions in the
report. If the owner (GitHub account) is unknown, use the placeholder `example` and say so.

## Layout and registry facts

The repository root is the provider repository; use a `terraform-provider-<name>/` subdirectory only
when the working directory already holds another project.

```text
main.go  go.mod  GNUmakefile  terraform-registry-manifest.json
internal/client/      # no Terraform imports
internal/provider/    # provider.go, <noun>_resource.go, <noun>_data_source.go, <noun>_model.go, tests
examples/  docs/
.github/workflows/    # test.yml, release.yml
.goreleaser.yml  .golangci.yml  CHANGELOG.md  README.md  LICENSE
```

No `cmd/` directory, no vendoring. The module path is `github.com/<owner>/terraform-provider-<name>`.
The registry address is `registry.terraform.io/<owner>/<name>`; consumers write
`source = "<owner>/<name>"`. Code skeletons: [references/PROVIDER.md](references/PROVIDER.md).

## Versions

Write `go.mod` first. Resolve the framework, plugin-go and plugin-testing versions with
`go list -m <module>@latest`; never copy remembered numbers. If a lookup fails, do not retry: use
what the module cache has, and tell the user to run
`go get github.com/hashicorp/terraform-plugin-framework@latest && go mod tidy`. Never fabricate
`go.sum`.

Libraries: `terraform-plugin-framework` (with its `provider`, `resource`, `datasource`, `types`,
`path`, `providerserver` and plan-modifier packages), `terraform-plugin-go` (`tfprotov6`),
`terraform-plugin-testing` (`helper/resource`, `helper/acctest`), optionally
`terraform-plugin-framework-validators` and `terraform-plugin-framework-timeouts`,
`terraform-plugin-mux` only for an SDKv2 migration, and `tfplugindocs` as a `tool` directive.
Never `github.com/hashicorp/terraform-plugin-sdk/v2` in a new provider.

## Configs

Copy from `assets/`:

| Asset | Destination | Notes |
|---|---|---|
| `golangci.yml` | `.golangci.yml` | golangci-lint v2 format |
| `goreleaser.yml` | `.goreleaser.yml` | exact `.yml` extension; edit only the `<NAME>` placeholder in `project_name` |
| `terraform-registry-manifest.json` | same name at the root | protocol `6.0` |
| `GNUmakefile` | `GNUmakefile` | |
| `github-test.yml` | `.github/workflows/test.yml` | refresh the Terraform matrix first |
| `github-release.yml` | `.github/workflows/release.yml` | |

`main.go` carries two `//go:generate` lines: `terraform fmt` over `./examples/`, and
`go tool tfplugindocs generate --provider-name <name>`. Only GitHub Actions workflows are
generated; no other CI files.

## Implementation rules

- `Configure` builds one client and passes it through `ProviderData`, `ResourceData` and
  `DataSourceData`.
- State comes from API responses, not from the plan.
- `Read` removes the resource from state on not found; `Delete` tolerates not found.
- Every resource has `ImportState`.
- `RequiresReplace` for attributes that cannot change in place; `UseStateForUnknown` for stable
  computed ones.
- Unset optional attributes stay null after read.
- Credentials are `Sensitive`, optional in the schema with an environment fallback, and are never
  defaulted or logged.
- Return diagnostics, never panic.
- Acceptance tests run against an in-process fake API unless the user supplies a real endpoint, so
  CI needs no credentials.

Client, resources, model conversion, schema decisions and SDKv2 migration:
[references/CREATION.md](references/CREATION.md).

## Validation loop

```text
gofmt -l .               # repeat until it prints nothing
go build ./...
go vet ./...
golangci-lint run ./...
go test ./...
actionlint .github/workflows/*.yml
```

Docs: `go generate ./...`, or tfplugindocs followed by `terraform fmt -recursive examples/`.
`TF_ACC=1 go test ./...` runs the acceptance tests against the fake API; a real API only on the
user's request with their own environment. Network-dependent commands can fail in a sandbox: report
the error. Details: [references/VALIDATION.md](references/VALIDATION.md).

## Release

The user tags `vX.Y.Z` on `main`. The workflow imports the GPG key from the secrets
`GPG_PRIVATE_KEY` and `PASSPHRASE` with `crazy-max/ghaction-import-gpg@v7`, goreleaser builds and
signs the checksums, and publishes the GitHub release; the registry ingests it. Setting the
secrets, registering the public key and the first registry publish are user steps. Full flow:
[references/RELEASE.md](references/RELEASE.md).

## Safety

- No commit, push, tag, repository creation or pull request without the user. Commits use
  `git commit -s`.
- Never `apply` or `destroy`, and never `plan` against a real API.
- No tokens or keys in commands, files or the transcript.

## Related

- `terraform:module-creator` for modules.
- Agent `terraform:terraform-engineer` for state and plan review.
