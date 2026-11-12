# Configuration schemas, env vars and constructor parameters

Every entry: **Bites**, **Spot**, **Fix**. Applies to config files, structs, CLI flags and
environment variables in any language.

### Zero, empty and null with a meaning

- **Bites:** `max_attempts: 0` means unlimited, `lifetime: 0` means forever, an empty API key in
  config equals an empty key in the request, `null` means "skip the check".
- **Spot:** every numeric limit and every secret field: what does its zero value do?
- **Fix:** the zero value is the safest one, or it is rejected at load time.

### Boolean traps

- **Bites:** `insecure: true` one typo away; `"false"` as a string is truthy; `disable_tls:
  false` forces a double negative; `verify: no` parses differently in YAML 1.1 and 1.2.
- **Spot:** flags that switch a control off, string-typed booleans, negated names.
- **Fix:** positive names (`verify_tls`), real booleans, strict parsing that rejects strings.

### Magic sentinel values

- **Bites:** `-1`, `"*"`, `"any"`, `"none"` or `"disabled"` turn a limit or allowlist into
  "everything".
- **Spot:** documentation or code that special-cases one value of an otherwise normal field.
- **Fix:** separate explicit fields for the wide-open case, off by default and logged loudly.

### Settings that contradict each other

- **Bites:** `auth_required: true` with `allow_anonymous: true`; `secure_cookies: true` behind
  `force_http: true`; a flag, an env var and a file all set and nobody knows which wins.
- **Spot:** pairs of related settings with no cross-check; precedence that is not written down.
- **Fix:** validate combinations at startup and refuse to start; document and test precedence.

### Environment variable hazards

- **Bites:** secrets in env show up in `ps e`, `/proc/<pid>/environ`, `docker inspect` and
  crash dumps; `APP_SKIP_AUTH=1` in a leftover `.env` turns a control off in production.
- **Spot:** env reads of secrets; env names that disable or downgrade security.
- **Fix:** secrets from files or a secret store; no env switch that can lower security.

### Paths from configuration

- **Bites:** `upload_dir: ../../etc` or an absolute path escapes the intended root.
- **Spot:** paths joined to a base without resolving and checking the prefix.
- **Fix:** resolve, then confine (`filepath.Rel`, `Path.resolve().is_relative_to`); reject
  symlinks out of the root.

### Constructor parameters taken as given

- **Bites:** an algorithm string with no allowlist, a timeout checked only for `> 0`, a URL that
  is never parsed so `http://` or `file://` slips through, a safe default replaced by any
  override without checks.
- **Spot:** constructors and `New*` functions that store parameters without validating them.
- **Fix:** validate in the constructor, both bounds for numbers, scheme and host for URLs, and
  return an error instead of a half-built object.
