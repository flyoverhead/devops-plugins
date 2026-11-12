# Risk patterns for diffs

What to look for in a hunk, by family. Each entry names the change that matters, not the code
that is merely present: the question is always what the diff added or took away. CI workflows
have their own files, read GitHub Actions first: `ci-github-actions.md`,
then `ci-gitlab.md`.

## Contents

- Quick greps
- Tier triggers by stack
- Security regressions
- Validation removed or weakened
- Authentication and authorisation
- Injection
- Paths and files
- TLS and crypto
- Secret handling
- Terraform exposure
- Ansible
- Errors, races, resource limits

## Quick greps

Run these over the range before reading hunks. Each lists the files whose added or removed
lines match (`-G` looks at both sides); open the hunk to see which side it is. A listed file is
HIGH until you have read it.

Dangerous tokens:

```bash
git diff --no-ext-diff --no-textconv -G'InsecureSkipVerify|verify=False|curl -k|--insecure|NODE_TLS_REJECT_UNAUTHORIZED|shell=True|yaml\.load\(|eval\(|exec\.Command\("(ba)?sh"|0\.0\.0\.0/0|chmod 0?77|mode: .?0?777|no_log: false|validate_certs: (false|no)|math/rand|md5|sha1' --name-only <range>
```

Check keywords (a hit on the removed side is the interesting one):

```bash
git diff --no-ext-diff --no-textconv -G'auth|verify|validate|require|assert|permission|csrf|no_log|RootCAs|MinVersion|allow_?list|sanitiz|escape' --name-only <range>
```

CI triggers, images, includes and permissions:

```bash
git diff --no-ext-diff --no-textconv -G'on:|pull_request_target|workflow_run|permissions|uses:|rules:|only:|except:|image:|include:|allow_failure|secrets' --name-only <range> -- '.github/workflows/*' '.github/actions/*' '.gitlab-ci.yml' '*.gitlab-ci.yml'
```

## Tier triggers by stack

| Stack | HIGH when the diff touches |
|---|---|
| Go | `crypto/*`, `tls.Config`, `http.Handler` chains and middleware order, `exec.Command`, `database/sql` query strings, `filepath.Join` with request data, `encoding/gob`, `yaml.Unmarshal` into `interface{}` |
| Python | `subprocess`, `os.system`, `pickle`, `yaml.load`, `requests(..., verify=)`, `jwt.decode` options, ORM `raw()` / `extra()` |
| Bash | `eval`, unquoted `$var` in commands, `set -x` near secret commands, `curl \| sh`, temp files under fixed `/tmp` names |
| TypeScript | `child_process`, `innerHTML` / `dangerouslySetInnerHTML`, `rejectUnauthorized`, cookie flags, CORS origin lists |
| Terraform | security groups and rules, IAM policies and bindings, public IPs and listeners, `sensitive`, `validation`, `lifecycle.prevent_destroy`, provider `insecure` |
| Ansible | `become`, `no_log`, `validate_certs`, `mode`, `shell` / `command` with templated input, `remote_src`, `when` guards on security tasks |
| CI | jobs holding secrets, trigger rules, images, includes, workflow `permissions` |

MEDIUM: business rules, state transitions, new endpoints, flags or dependencies. LOW: comments,
docs, log text, tests (unless a test is the only proof of a security property).

## Security regressions

- A line deleted by this diff was added by a commit whose message says fix, security or CVE.
- A line added by this diff matches one that a security commit removed earlier
  (`git log -S'<text>'` shows both commits).
- A refactor moves a check into a helper that one of the call sites no longer calls.

## Validation removed or weakened

- A regex loses its `^` or `$` anchor, or `\A` / `\z`.
- A size, count or length limit goes up by an order of magnitude or disappears.
- An allow-list becomes a deny-list, or a list of accepted values gains a wildcard.
- A type check turns into a truthiness check (`if v:` accepts `"0"` and `"false"` too).

## Authentication and authorisation

- A route is registered outside the authenticated router group or before the middleware.
- Role checks by prefix (`strings.HasPrefix(role, "admin")` accepts `administrator-readonly`).
- An object is fetched by an ID from the request with no ownership check (IDOR).
- A token or HMAC compared with `==` instead of `subtle.ConstantTimeCompare` / `hmac.compare_digest`.
- A default role or scope widens for new users.

## Injection

- Command: `exec.Command("sh", "-c", s)` with `s` built from input; Python `shell=True`;
  unquoted `$1` in Bash; Ansible `shell:` with `{{ var }}` in the command line.
- SQL: query text assembled with `+`, `fmt.Sprintf` or f-strings instead of placeholders.
- Templates: `template.HTML(...)` over user data, Jinja2 `| safe`, `autoescape=False`.
- Deserialisation: `yaml.load` without `SafeLoader`, `pickle.loads`, `gob` from the network.

## Paths and files

- `filepath.Join(root, name)` / `os.path.join` with request data and no containment check after
  `Clean` / `realpath`.
- Archive extraction that does not reject entries containing `..` or absolute paths.
- Fixed names under `/tmp` instead of `mktemp` / `os.CreateTemp`.
- Modes widened to `0666` / `0777`, or a secret file created without an explicit mode.

## TLS and crypto

- Verification off: `InsecureSkipVerify: true`, `verify=False`, `curl -k`,
  `NODE_TLS_REJECT_UNAUTHORIZED=0`, `rejectUnauthorized: false`.
- A `VerifyPeerCertificate` callback that returns `nil` on paths it does not recognise.
- Pinned roots (`RootCAs`, `cafile`) removed, so the system store or nothing is trusted.
- `MinVersion` lowered or dropped.
- A switch that turns verification off read from the environment, where *any* non-empty string
  enables it, `"false"` and `"0"` included.
- `math/rand` / `random` for tokens, keys or nonces; MD5 or SHA-1 for anything that must resist
  forgery.

## Secret handling

- A whole config struct logged or printed (`%+v`, `json.dumps(settings)`).
- `set -x` left on around commands that take a token.
- `.env` or credential files committed; a token passed on the command line (visible in `ps`).
- Error messages that echo a connection string or header with the credential in it.
- A secret moved out of a secret store into a plain variable, file, log or unmasked CI variable.

## Terraform exposure

- An ingress rule or security group opened to `0.0.0.0/0` or `::/0`.
- A new public listener, load balancer, floating IP or public bucket ACL.
- A provider block gains `insecure = true` or skips TLS checks.
- `sensitive = true` dropped from an output or variable that carries a credential.
- A `validation` block removed or loosened.
- IAM policies with `"*"` actions or resources; broader role bindings.
- `prevent_destroy` removed from a stateful resource.

## Ansible

- `no_log: true` removed from a task that handles a password or token.
- `validate_certs: false` on `uri`, `get_url` or a package repository task.
- `become: true` added to tasks that do not need root.
- File or directory `mode` widened; a key or config written world-readable.
- `remote_src: true` fetching from a source the play does not control.
- A `when:` guard on a hardening or security task made looser or removed.
- A role default that is a working password instead of an empty value that fails.

## Errors, races, resource limits

- The error from a security call is discarded (`_ =` on `Verify`, `chmod`, `setuid`).
- Check-then-use on a path or a permission (TOCTOU) instead of operating on the opened handle.
- A request body read without a size limit (`io.ReadAll(r.Body)` with no `MaxBytesReader`).
- A regex compiled from input; a timeout or deadline removed from a network call.
