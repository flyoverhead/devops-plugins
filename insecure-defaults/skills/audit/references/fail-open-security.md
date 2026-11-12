# Checks that fail open

**Report when:** a check that protects something (TLS verification, authentication, CSRF,
signature validation, a CI security gate) is off by default, off when its setting is missing,
or silently ignored when it fails.

**Skip when:** the switch is off only in a test or local-development profile that cannot be
selected in production, the "insecure" flag targets loopback, or a missing setting makes the
process stop instead of continuing unchecked.

A fail-open default turns an operator's omission into an outage of a control that nobody
notices, because everything keeps working. Look for two shapes: the literal "off" (always
exploitable) and the lookup whose missing-value branch is "off" (exploitable wherever the
deployment forgets the key). Both need a sink: the line where the flag actually skips the check.

## Contents

- Vulnerable examples (12): Python, JavaScript, Go, Bash, HCL, Ansible, GitHub Actions
- Secure examples (6): fail-secure lookups, scoped exceptions

## Vulnerable examples

**Requests without certificate checks (Python)**

```python
# File: sync/client.py
resp = requests.get(upstream_url, timeout=10, verify=False)
```

Risk: any on-path attacker can impersonate the upstream.

**Auth toggle that defaults to off (Python)**

```python
# File: admin/settings.py
REQUIRE_LOGIN = os.getenv("ADMIN_REQUIRE_LOGIN", "false") == "true"
```

Risk: the admin views skip login unless someone remembers to set the variable.

**CSRF disabled in the base config (Python)**

```python
# File: shop/config.py
WTF_CSRF_ENABLED = False
CSRF_PROTECT = False
```

Risk: every form accepts cross-site posts.

**Verification flag read with `||` (JavaScript)**

```javascript
// File: gateway/src/upstream.js
const verifyPeer = process.env.UPSTREAM_VERIFY || "false";
```

Risk: the agent created from this flag sets `rejectUnauthorized: false` when it is
the string "false".

**TLS rejection disabled for the whole process (JavaScript)**

```javascript
// File: scripts/import.js
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";
```

Risk: switches off verification for every HTTPS call in the process, not just one.

**`InsecureSkipVerify` (Go)**

```go
// File: internal/billing/client.go
tlsCfg := &tls.Config{
	MinVersion:         tls.VersionTLS12,
	InsecureSkipVerify: true,
}
client := &http.Client{Transport: &http.Transport{TLSClientConfig: tlsCfg}}
```

Risk: the payment client trusts whatever certificate it is shown, so a proxy on the path reads card numbers.

**Webhook signature check off unless enabled (Go)**

```go
// File: internal/hooks/verify.go
verifyHooks := envOr("HOOKS_VERIFY", "false") == "true"
```

Risk: unsigned webhooks are accepted by default.

**Curl without verification (Bash)**

```bash
# File: install.sh
curl -fsSLk https://get.example.dev/agent.sh | sh
```

Risk: a script piped to a shell from an unverified connection is remote code execution
for anyone on the path.

**Provider with TLS off (HCL)**

```hcl
# File: envs/prod/provider.tf
provider "vault" {
  address         = "https://secrets.example.internal:8200"
  skip_tls_verify = true
}
```

Risk: the provider sends its token to whoever answers.

**Role default that skips certificate checks (Ansible)**

```yaml
# File: roles/edge_agent/defaults/main.yml
edge_agent_validate_certs: false
```

Risk: the `get_url` task downloads a binary that later runs as a service.

**Security gate that cannot fail (GitHub Actions workflow)**

```yaml
# File: .github/workflows/ci.yml
- name: Container scan
  run: trivy image --exit-code 1 app:ci || true
- name: Licence scan
  uses: fossa-contrib/fossa-action@v3
  continue-on-error: true
```

Risk: both gates report green whatever they find; merges proceed regardless.

**Publish after a failed check (GitHub Actions workflow)**

```yaml
# File: .github/workflows/release.yml
- name: Publish
  if: always()
  run: npm publish
```

Risk: `always()` runs the publish even when the test or scan step failed.

## Secure examples

**Required verification setting (Python)**

```python
# File: admin/settings.py
REQUIRE_LOGIN = os.environ.get("ADMIN_REQUIRE_LOGIN", "true") != "false"
```

Holds because: the missing case keeps the check on; turning it off needs an explicit value.

**Crash if the CA bundle is missing (Go)**

```go
// File: internal/billing/client.go
pem, err := os.ReadFile(cfg.CAFile)
if err != nil {
	log.Fatalf("billing CA bundle: %v", err)
}
```

Holds because: the client never starts with a weaker trust store.

**Verified download (Bash)**

```bash
# File: install.sh
curl -fsSL --proto '=https' --tlsv1.2 -o agent.tgz "$AGENT_URL"
echo "${AGENT_SHA256}  agent.tgz" | sha256sum -c -
```

Holds because: TLS verification stays on and the artifact is checked against a pinned digest.

**Insecure only against a local dev server (HCL)**

```hcl
# File: envs/dev/provider.tf
provider "vault" {
  address         = "https://127.0.0.1:8200"
  skip_tls_verify = true
}
```

Holds because: dev-only root module that targets loopback; refuted at step 1. Report it if prod
reuses this file.

**Validation follows the default (Ansible)**

```yaml
# File: roles/edge_agent/tasks/install.yml
- name: Download edge agent
  ansible.builtin.get_url:
    url: "{{ edge_agent_url }}"
    dest: /tmp/edge-agent.tgz
    checksum: "sha256:{{ edge_agent_sha256 }}"
    mode: "0644"
```

Holds because: `validate_certs` keeps its module default (on) and a checksum pins the artifact.

**Scan gate that blocks (GitHub Actions workflow)**

```yaml
# File: .github/workflows/ci.yml
- name: Container scan
  run: trivy image --exit-code 1 --severity HIGH,CRITICAL app:ci
```

Holds because: a finding fails the job and the required check.
