# Releasing a provider

## Contents

- Flow
- Repository requirements
- Workflows
- Secrets
- Cutting a release
- Versioning
- Verified and not verified

## Flow

The user pushes a tag `v*`. `release.yml` starts, and goreleaser builds the zips, a checksums
file, a detached signature, and attaches the registry manifest. The result is a GitHub release,
which the Terraform Registry picks up and ingests.

Release assets, for a project named `terraform-provider-inventory`:

| Asset | Name |
|---|---|
| Binary archive | `<project>_<ver>_<os>_<arch>.zip` |
| Checksums | `<project>_<ver>_SHA256SUMS` |
| Detached signature | `<project>_<ver>_SHA256SUMS.sig` |
| Registry manifest | `<project>_<ver>_manifest.json` |

## Repository requirements

- A public GitHub repository named `terraform-provider-<name>`, default branch `main`.
- A `LICENSE` the registry recognises.
- `docs/` generated and committed.
- `terraform-registry-manifest.json` at the root: `version` 1 and
  `metadata.protocol_versions` of `["6.0"]`.
- The `Address` in `main.go` equals `registry.terraform.io/<owner>/<name>`.
- The goreleaser config is named `.goreleaser.yml`, with that exact extension.

## Workflows

Only GitHub Actions workflows are generated; no other CI files.

`test.yml`: runs on push and pull request, ignoring `README.md`. Jobs: build with lint; generate
with a diff check that fails when generated files are stale; the acceptance matrix over the two
latest Terraform minor releases (`<major>.<minor>.*`, see the CI matrix section in
`VALIDATION.md`), with `terraform_wrapper: false`, `TF_ACC: '1'` and
`go test ./internal/provider/`.

`release.yml`: triggers on tags `v*`, with `permissions: contents: write`. Steps: checkout with
`fetch-depth: 0`; `setup-go` reading the version from `go.mod`; `crazy-max/ghaction-import-gpg@v7`
with the two secrets; the goreleaser action running `release --clean` with `GITHUB_TOKEN` and
`GPG_FINGERPRINT` taken from the import step's output.

Action majors in the assets were current when written; re-check them against each action's
releases before copying:

| Action | Major |
|---|---|
| `actions/checkout` | `v7` |
| `actions/setup-go` | `v7` |
| `golangci/golangci-lint-action` | `v9` |
| `hashicorp/setup-terraform` | `v4` |
| `crazy-max/ghaction-import-gpg` | `v7` |
| `goreleaser/goreleaser-action` | `v7` |

Keep the workflows clean under `actionlint`.

## Secrets

| Secret | Content |
|---|---|
| `GPG_PRIVATE_KEY` | armored private key |
| `PASSPHRASE` | passphrase of that key |
| `GITHUB_TOKEN` | provided by GitHub |

The user sets the first two in the repository settings and registers the matching public key once
in the registry's signing-key settings. The assistant never handles key material.

## Cutting a release

1. Commit the CHANGELOG entry and the generated docs.
2. The user creates and pushes the tag. The assistant does not.
3. Watch the run with `gh run list --workflow release.yml` and `gh run watch`.
4. For the first release only: sign in to the registry, publish the provider from the repository,
   and add the public signing key.
5. Consumers pin with `~>`.

## Versioning

Semantic versioning. Before 1.0.0 a breaking change bumps MINOR. Removing or renaming a resource or
an attribute, and anything that forces replacement for an unchanged configuration, is breaking.

## Verified and not verified

Verified locally: `actionlint`, `goreleaser check`, build, vet and lint. Not verifiable without the
user: the tag-triggered run, the secrets, and registry ingestion. Report those as not run.
