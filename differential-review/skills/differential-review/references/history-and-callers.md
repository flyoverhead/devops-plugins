# History and callers

Commands for steps 4 and 6. Everything here is read-only: `git log`, `git show`, `git blame`,
`git grep` and plain `grep`. `git grep` is not pre-allowed, so each call prompts. The base side is
always read with `git show --no-ext-diff --no-textconv <base>:<path>`, never by checking it out.

## Contents

- Where a removed line came from
- Is an added line coming back?
- Reading the result
- Counting callers
- Other repositories
- Writing the numbers down

## Where a removed line came from

Take a distinctive fragment of the deleted line (an identifier or a literal, not whitespace):

```bash
git log -S'RootCAs: pool' --oneline -- internal/vault/client.go
git log -S'RootCAs: pool' --format='%h %ad %s' --date=short -- internal/vault/client.go
```

The oldest hit is usually the commit that introduced the line; the newest is the one removing
it (your range). Confirm the origin and see its neighbours with blame on the base:

```bash
git blame -L 24,30 base -- internal/vault/client.go
git show --no-ext-diff --no-textconv --stat <origin-sha>
```

For a renamed file, add `--follow` to `git log`. For a block that moved between files, search
without a path: `git log -S'<fragment>' --oneline`.

## Is an added line coming back?

Search the whole history for new risky lines, with patches so you can see both directions:

```bash
git log --no-ext-diff --no-textconv -S'InsecureSkipVerify' -p --format='--- %h %s' -- internal/
```

Pattern of a regression: the string was added in commit A, removed in commit B whose message
says fix / security / CVE, and the diff under review adds it (or an equivalent) again. Name B by
sha and subject in the report's History section.

Equivalents count. `InsecureSkipVerify = true` behind an environment switch re-introduces the
same exposure as the literal `true` it once replaced.

## Reading the result

| Origin of the removed code | Starting severity |
|---|---|
| Commit subject or body mentions fix, security, vuln, CVE, CWE, hardening | CRITICAL until shown otherwise |
| Added within the last 30 days, removed now | HIGH |
| Old, ordinary commit | the tier from triage |

"Shown otherwise" means you found the same protection somewhere the changed path still passes
through: a caller that validates, middleware that still runs, a config that still pins. Cite
that `path:line`.

## Counting callers

Exclude tests and vendored code unless the change is in a test helper. The commands below are
`git grep`, which prompts. On the checked-out tree, the Grep tool with the same pattern and a
`glob` per file type gives the same count without a prompt; drop test and vendor hits by path.

| Changed thing | Command |
|---|---|
| Go function or method | `git grep -n 'Read(' -- '*.go' ':!*_test.go' ':!vendor/'`, then drop false hits by reading |
| Go package | `git grep -n '"example.org/app/internal/vault"' -- '*.go'` |
| Python function | `git grep -nE '\bload_settings\(' -- '*.py' ':!tests/'` |
| Bash function or script | `git grep -nE '(^|[^a-z_])rotate_keys\b|bin/rotate-keys' -- '*.sh' '*.yml' 'Makefile'` |
| TypeScript export | `git grep -nE "from ['\"].*/session['\"]" -- '*.ts' '*.tsx'` |
| Terraform module | `git grep -n 'source *= *".*modules/network' -- '*.tf'` |
| Terraform variable | `git grep -n 'var\.allowed_cidrs' -- '*.tf'` |
| Ansible role | `git grep -nE '(role|name): *(\S+\.)?nginx_hardening\b' -- '*.yml' '*.yaml'` |
| Ansible role variable | `git grep -n 'nginx_hardening_tls_protocols' -- '*.yml' '*.yaml' '*.j2'` |
| GitHub reusable workflow or composite action | `git grep -n 'uses: *\./\.github/workflows/release\.yml' -- '.github/'` |
| GitLab include | `git grep -n 'templates/deploy\.yml' -- '*.yml'` |

## Other repositories

When the user names a GitHub owner and `gh` works:

```bash
gh search code --owner acme-tools 'internal/vault' --limit 100
gh search code --owner acme-tools 'uses: acme-tools/workflows/.github/workflows/release.yml'
```

Search results are capped and indexing lags, so the count is a floor. Without `gh`, or for
another host, search the local checkouts the user points you to, one call per checkout:

```bash
git -C ~/src/edge-proxy grep -l 'nginx_hardening'
git -C ~/src/web-gateway grep -l 'nginx_hardening'
```

`git -C` is not pre-allowed, so each call asks for approval. The skill only ever uses it as
`git -C <dir> grep`.

## Writing the numbers down

- In the report, give the count, the band and the command that produced it.
- Cross-repository counts are "at least N"; say which owner or which local checkouts were
  searched and which were not.
- Bands: 1–5 LOW, 6–20 MEDIUM, 21–50 HIGH, more than 50 CRITICAL.
