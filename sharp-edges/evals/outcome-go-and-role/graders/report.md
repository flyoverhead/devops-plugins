---
type: llm
---

Fixture facts:
- tokens/tokens.go: `NewMinter(secret string, ttl time.Duration)` (line 19). `Check` returns true for any token when the secret is empty (lines 41-43); the README example and cmd/gatectl/main.go build the minter from `os.Getenv("GATE_TOKEN_SECRET")`, so an unset variable accepts every token. A ttl of 0 mints tokens with expiry 0, which `Check` treats as never expiring (lines 26-28 and 56). The MAC is compared with `!=` on hex strings (line 49), not a constant-time compare.
- roles/edge_proxy/defaults/main.yml: `edge_proxy_backend_validate_certs: false`, `edge_proxy_trusted_cidrs` defaults to `0.0.0.0/0`, `edge_proxy_admin_password` defaults to an empty string; meta/argument_specs.yml has no `required`, `choices` or validation for them. tasks/main.yml also splices the user and password into a `shell` htpasswd command line.

PASS only if the final response does all of the following:
1. reports that an empty secret/key makes `Check` accept any token, with a design fix (for example refuse an empty key in the constructor or return an error, fail closed);
2. reports that a zero ttl disables expiry, with a design fix (for example reject zero/negative ttl, require an explicit option for non-expiring tokens, or apply a bounded default);
3. reports the non-constant-time MAC comparison, with a fix such as `hmac.Equal` or `subtle.ConstantTimeCompare`;
4. reports insecure role defaults, covering `validate_certs` false plus at least one of the open `0.0.0.0/0` network default or the empty admin password, with a design fix (flip the default, drop the default and make it required, assert or validate);
5. gives file locations for the findings (file name with a line number for at least most of them).

Reporting the shell command built from the password, or other extra findings, is fine. FAIL if any numbered item is missing, or if the response says it edited or created files in the repository.
