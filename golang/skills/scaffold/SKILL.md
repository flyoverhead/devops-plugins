---
name: scaffold
description: Scaffolds a new Go project on GitHub, only when invoked as /golang:scaffold <name> <cli|service|library> - module path from the argument or the origin remote, installed Go version, cmd/ and internal/ layout, GitHub Actions CI and release workflows, goreleaser v2, a GHCR image for services, CHANGELOG and DCO sign-off. User-invoked only; never starts on its own.
argument-hint: "<name> <cli|service|library> [module-path]"
disable-model-invocation: true
allowed-tools: Read Write Edit Glob Bash(go version*) Bash(date +%F) Bash(go mod:*) Bash(go build:*) Bash(go vet:*) Bash(gofmt:*) Bash(mkdir:*) Bash(git init:*) Bash(git status:*) Bash(git remote get-url:*)
---

# Scaffold a Go project

Arguments: $ARGUMENTS

Injected context, captured before this skill was sent to you:

- Toolchain: !`go version`
- Date: !`date +%F`

The toolchain line above is already captured. Do not run the toolchain version command again. If the toolchain line is empty, or is an error instead of a `go version go...` line, stop and ask the user to install Go.

## Arguments

| Position | Meaning |
|---|---|
| 1 | `name`: lowercase kebab-case. Used as the binary name, the `cmd/` directory and the repository name. Required. |
| 2 | kind: `cli`, `service` or `library`. Default `cli`. |
| 3 | module path. Optional. |

If `name` is missing, ask for it and stop.

## Checklist

- [ ] Parse the arguments and resolve `MODULE` (next section).
- [ ] Take `GO_VERSION` from the injected line: `go1.27.1` becomes `1.27.1`. `DATE` is the injected date.
- [ ] Choose the target directory and list what already exists there.
- [ ] Run `go mod init <MODULE>`, unless `go.mod` exists; then keep its module path.
- [ ] Create the layout for the kind: read each template with the Read tool from `${CLAUDE_SKILL_DIR}/references/templates/`, substitute `<NAME>`, `<MODULE>`, `<OWNER>`, `<GO_VERSION>`, `<KIND>`, `<DATE>`, and write the result.
- [ ] Confirm the workflows match the kind.
- [ ] Write `README.md` and `.gitignore`.
- [ ] Validate until it exits 0 with no gofmt output: `go mod tidy && gofmt -l . && go vet ./... && go build ./...`.
- [ ] Run `git status`. Run `git init` if the directory is not a repository. Do not commit.
- [ ] Report the file tree, the validate output and the next steps.

## Module path

1. The third argument, verbatim.
2. Otherwise convert the output of `git remote get-url origin`: both `git@github.com:acme/tool.git` and `https://github.com/acme/tool.git` become `github.com/acme/tool`.
3. Otherwise ask and stop. Never invent a path.

`OWNER` is the second path element of `MODULE`, lowercased, because GHCR image names must be lowercase. A module outside `github.com/` has no GitHub owner: for a service, ask for the owner before writing any service file.

## Target

Scaffold in place when the current directory has no `go.mod`, no `.go` files and no visible entries other than `README.md`, `LICENSE` and `.gitignore`. Hidden tool directories (`.git/`, `.claude/`, `.idea/`, `.vscode/`) do not count. Otherwise create `./<name>/` and scaffold there.

Never overwrite an existing file. Show the diff and ask. Only GitHub Actions workflows are generated; never create `.gitlab-ci.yml` or any other CI configuration.

## Layout

| Kind | Files |
|---|---|
| `cli` | `cmd/<name>/main.go`, `internal/`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.goreleaser.yml`, `.golangci.yml`, `CHANGELOG.md` |
| `service` | `cmd/<name>/main.go`, `internal/`, `ci.yml`, `release.yml` (service variant), `.goreleaser.yml` with the docker block appended, `Dockerfile`, `.golangci.yml`, `CHANGELOG.md` |
| `library` | `<pkg>.go` with a package doc comment, `<pkg>_test.go`, `ci.yml`, `.golangci.yml`, `CHANGELOG.md`. No `cmd/`, release workflow, goreleaser config or Dockerfile. |

For a library, `<pkg>` is the last element of `name` with the dashes removed, and it is also the package name.

| Template | Destination |
|---|---|
| `main-cli.go.tmpl` (cli) or `main-service.go.tmpl` (service) | `cmd/<name>/main.go` |
| `github-ci.yml` | `.github/workflows/ci.yml` |
| `github-release.yml` (cli) or `github-release-service.yml` (service) | `.github/workflows/release.yml` |
| `goreleaser.yml`, plus `goreleaser-docker.yml` appended for a service | `.goreleaser.yml` |
| `golangci.yml` | `.golangci.yml` |
| `Dockerfile` | `Dockerfile` |
| `CHANGELOG.md` | `CHANGELOG.md` |

## Why these names and shapes

- The file is `.goreleaser.yml`, exactly. goreleaser prefers it over `.yaml`, and a sibling `.yaml` file is silently ignored.
- `main` declares `Version`, `Commit` and `Date`, which the release sets through the ldflags `main.Version`, `main.Commit` and `main.Date`. The build target is `./cmd/<name>`.
- The service template runs its own mux and serves pprof on `127.0.0.1:6060`. It never uses `http.DefaultServeMux`.
- Goreleaser builds and pushes the service image with `dockers_v2` to `ghcr.io/<OWNER>/<name>`. The Dockerfile only copies a prebuilt binary from `$TARGETPLATFORM/` and has no build stage, so a plain `docker build .` fails. Test the image path with `goreleaser release --snapshot --clean`.
- `.golangci.yml` uses the v2 format (`version: "2"`), matching the `v2.x` golangci-lint version pinned in the CI workflow.
- CHANGELOG sections are ISO dates.

## Workflows

- `ci.yml` runs on pushes to the default branch `main` and on pull requests: vet, golangci-lint, `go test -race ./...`, govulncheck.
- `release.yml` runs on `v*` tags and runs goreleaser (`version: ~> v2`), which publishes a GitHub release. The service variant also logs in to GHCR with `GITHUB_TOKEN`.
- Action major versions are pinned in the templates. Do not change them unless asked.

## README and gitignore

`README.md` has: a one-paragraph purpose; install (a release archive or `go install <MODULE>/cmd/<name>@latest`; for a service `docker pull ghcr.io/<OWNER>/<name>`; for a library `go get <MODULE>`); usage (cli: `<name> -version`; service: the environment variables `LISTEN_ADDR` and `DEBUG_ADDR`); development (`go test ./...`, `golangci-lint run`); release (push a `vX.Y.Z` tag).

`.gitignore` lists `/dist/`, `/<name>`, `*.test`, `cover.out` and `*.pprof`. It does not list `go.sum`.

## Next steps

Hand these to the user. Run none of them without a yes.

1. Create the GitHub repository: `gh repo create <owner>/<name> --private`, or in the web UI.
2. Make the first signed-off commit: `git add -A && git commit -s -m "feat: scaffold <name> <kind>"`.
3. Release by pushing a `vX.Y.Z` tag. No extra secrets are needed. For a service, the first push creates the GHCR package, so check its visibility and repository access afterwards.
4. For service design questions, use `golang:golang-architect`.

## Limits

- `go test` and `go vet`: never `-exec`, `-toolexec`, `-vettool` or `-overlay`; they run other
  programs in place of the toolchain's own.
- `go build`: never `-toolexec`, `-overlay` or `-o`; they run other programs or write the
  binary over any path. `go build ./...` is enough to prove the code compiles.
