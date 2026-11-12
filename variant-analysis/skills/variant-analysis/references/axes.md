# Root cause and search axes

## Contents

- [The root-cause sentence](#the-root-cause-sentence)
- [Where copies come from](#where-copies-come-from)
- [Axis kinds](#axis-kinds)
- [Is it a real axis?](#is-it-a-real-axis)
- [Sinks by language](#sinks-by-language)
- [Infrastructure starters](#infrastructure-starters)

## The root-cause sentence

Read the original location and its enclosing function before writing anything. Then answer:

| Question | Example answer (mirror-sync daemon) |
|---|---|
| What is the dangerous operation? | a shell parses a string: `exec.Command("sh", "-c", s)` |
| Which data makes it dangerous? | the branch name in an unsigned webhook payload |
| Which protection is missing? | argv form with `--` before the ref, or `git check-ref-format` |
| What context lets it happen? | the webhook endpoint skips the signature check |

Fold the answers into one line and keep it in front of you for the whole hunt:

> Untrusted **X** reaches dangerous **Y** without protection **Z**.

Example: *a branch name from an unsigned webhook reaches a `sh -c` string without ever
being checked as a ref name.*

Logic bugs with no flow of data (an inverted check, a wrong default, an off-by-one in a
bounds check) get an invariant instead: *"`allowed()` must return false for an anonymous
caller; at `auth.go:41` it returns true when both IDs are empty."*

If the four answers do not come out cleanly, you do not understand the bug yet. Read more
of the original before searching.

## Where copies come from

Knowing why a variant would exist tells you where to look first:

- **Copy-paste.** Same function body, renamed variables. Start at level 1 of the ladder.
- **API misuse.** The API is easy to call wrongly; every call site is a suspect.
- **Framework idiom.** A tutorial pattern repeated per handler, per route, per task file.
- **One author's habit.** `git log --format='%an' -- <original path>` gives the author;
  `git log --author=<name> --name-only` lists what else they touched.
- **Half-done fix.** An earlier commit fixed one site; `git log -S '<sanitiser name>'`
  shows where the protection was added and which siblings it missed.

## Axis kinds

An axis is one direction in which the original can be widened. Enumerate candidates from
each kind, then keep only those that pass the test below.

1. **Same role, other identifiers.** Other variables, parameters, fields or config keys that
   carry the same kind of value (`branch`, `tag`, `remote`, `ref`). Grep that they exist
   before listing them.
2. **Other sinks for the same operation.** `exec.Command` with `sh -c` and also
   `exec.CommandContext`, `syscall.Exec`, `os/exec` wrappers in the repo, `subprocess` with
   `shell=True`, `os.system`, Node `exec`, a Bash `eval`.
3. **Logic shape errors.** Inverted conditions, wrong defaults, `||` where `&&` was meant,
   early returns that skip the check.
4. **Empty and boundary values.** Both IDs empty and therefore equal, zero, empty list,
   `nil` map, max int, negative length.
5. **Name says one thing, code does another.** Functions named `deny`, `block`, `validate`,
   `isAllowed` whose return value means the opposite at some call sites.
6. **Other layers of the same repo.** The Go handler, the wrapper script it calls, the
   Ansible task that templates the same value, the CI job that runs the script.

## Is it a real axis?

Keep an axis only if all three hold:

- it names concrete identifiers, functions or constructs you can put in a pattern;
- it does not overlap another axis (two sweeps over the same sinks waste a sweeper);
- `rg` shows at least one lead for it in this repository.

"Input validation problems" or "authorisation" is a theme, not an axis. "Every
`exec.Command*` call whose second argument is `"-c"`" is an axis.

## Sinks by language

| Language | Shell | SQL | File path | Markup |
|---|---|---|---|---|
| Go | `exec.Command(sh, "-c", …)`, `exec.CommandContext` | `db.Query/Exec/QueryRow(+Context)` with string building | `os.Open`, `os.ReadFile`, `http.ServeFile` | `template.HTML`, `template.JS` |
| Python | `subprocess.*(…, shell=True)`, `os.system`, `os.popen` | `cursor.execute` with `%`/f-string | `open`, `send_file` | `Markup`, `render_template_string` |
| Bash | `eval`, `sh -c "$x"`, `bash -c`, unquoted `$x` in a command word | `psql -c "$x"`, `mysql -e` | `cat "$dir/$x"` without `basename` | n/a |
| TS/JS | `child_process.exec/execSync`, `spawn(…, {shell: true})` | `db.query` with template strings, `$queryRawUnsafe` | `fs.readFile*`, `res.sendFile` | `innerHTML`, `dangerouslySetInnerHTML` |
| Terraform | `local-exec` `command` with interpolation | n/a | `file()` of a variable path | n/a |
| Ansible | `shell`, `command`, `raw` with `{{ }}` | `community.*.query` with `{{ }}` | `src: "{{ … }}"` from user vars | `template` of untrusted vars |

## Infrastructure starters

Patterns worth one `rg` each when the original sits in infra code. GitHub Actions comes
first; GitLab CI uses the same ideas with its own variable names.

**GitHub Actions** (`.github/workflows/*.yml`):

- `${{ github.event.* }}` (issue title, PR body, head ref, comment body) inside `run:`;
- `pull_request_target` or `workflow_run` jobs that check out the PR head
  (`ref: ${{ github.event.pull_request.head.sha }}`) and then run its code;
- actions referenced by tag or branch instead of a full commit SHA;
- `permissions: write-all` or no `permissions:` key on a workflow that handles PR input.

**GitLab CI** (`.gitlab-ci.yml`, included templates):

- `$CI_MERGE_REQUEST_TITLE`, `$CI_MERGE_REQUEST_DESCRIPTION`, `$CI_COMMIT_MESSAGE`,
  `$CI_COMMIT_BRANCH`, `$CI_COMMIT_REF_NAME` expanded inside `script:` without quoting,
  or passed to `eval`/`sh -c`.

**Ansible:** `ansible.builtin.shell`, `command` or `raw` whose arguments contain `{{ … }}`
fed from inventory, extra-vars or registered output; `command` with `argv:` is the safe form.

**Bash:** `eval "…$var…"`, `sh -c "…$var…"`, `bash -c`, `xargs sh -c`, unquoted expansions
in command position.

**Terraform:** `insecure = true`, `skip_tls_verify = true`, `allow_unverified_ssl = true`,
`insecure_skip_verify`, and `local-exec` commands built from variables.
