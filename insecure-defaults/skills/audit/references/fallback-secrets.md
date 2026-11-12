# Secrets with literal fallbacks

**Report when:** a signing key, session secret, salt, token or password gets a literal value
whenever its setting is absent or empty, and that value reaches a security decision.

**Skip when:** the absent setting stops the process (raising lookup, fatal exit, Terraform
`validation`, Ansible `assert`), the literal lives only in tests, fixtures or docs, or the
default is generated at start-up from a CSPRNG and never reused.

The question that decides a finding is not "is there a literal in the code?" but "will the
running service ever sign, encrypt or authenticate with that literal?". A literal that can
never execute is noise. A literal that executes whenever an operator forgets one variable is a
shared secret published in the repository: anyone who reads the source can forge what it
protects.

## Contents

- Vulnerable examples (14): Python, JavaScript, TypeScript, Ruby, Go, Bash, HCL, Ansible,
  GitHub Actions
- Secure examples (8): fail-when-unset in each stack, plus two non-findings

## Vulnerable examples

**Flask key read with a literal default (Python)**

```python
# File: billing/app.py
app.config["SECRET_KEY"] = os.environ.get("BILLING_FLASK_KEY", "billing-dev-key")
```

Risk: Flask signs session cookies with this value; an unset variable means every
deployment signs with a string from the repository.

**Django key committed as a literal (Python)**

```python
# File: portal/settings/prod.py
SECRET_KEY = "portal-prod-key-do-not-share"
```

Risk: unconditional; every environment that imports this module signs with it.

**Settings module using `or` (Python)**

```python
# File: portal/settings/base.py
JWT_SIGNING = os.getenv("PORTAL_JWT_KEY") or "portal-insecure-jwt"
```

Risk: an empty string and a missing variable both land on the literal.

**Express session secret with `||` (JavaScript)**

```javascript
// File: web/server.js
app.use(session({ secret: process.env.WEB_SESSION_SECRET || "keyboard-cat-web" }));
```

Risk: express-session signs the session id with it; forged cookies follow.

**Nullish fallback for a token key (TypeScript)**

```typescript
// File: api/src/auth/jwt.ts
const tokenKey = process.env.API_TOKEN_KEY ?? "api-fallback-signing";
```

Risk: `??` covers only undefined, but undefined is exactly the forgotten case.

**`ENV.fetch` with a default (Ruby)**

```ruby
# File: config/initializers/hooks.rb
HOOK_SECRET = ENV.fetch("HOOK_SECRET", "hooks-local")
```

Risk: `fetch` with a second argument never raises, so the guard is gone.

**Empty check that assigns a literal (Go)**

```go
// File: internal/session/key.go
k := os.Getenv("SESSION_KEY")
if k == "" {
	k = "session-dev-only"
}
```

Risk: the branch runs on every host that lacks the variable; the key then feeds
`hmac.New`.

**Helper with a default argument (Go)**

```go
// File: internal/config/env.go
webhookKey := envOr("WEBHOOK_SIGNING_KEY", "local-webhook-key")
```

Risk: the wrapper returns its second argument when the variable is missing, so every
caller of `envOr` is a fallback site.

**Viper default for a secret (Go)**

```go
// File: cmd/root.go
viper.SetDefault("auth.hmac_secret", "changeit-hmac")
```

Risk: viper serves the default when neither file nor environment sets the key.

**Package-level literal key (Go)**

```go
// File: internal/token/sign.go
var signingKey = []byte("static-token-signing-key")
```

Risk: unconditional; no configuration can replace it.

**Parameter expansion default (Bash)**

```bash
# File: scripts/start.sh
export APP_SECRET="${APP_SECRET:-start-sh-secret}"
```

Risk: the entrypoint exports the literal into the service environment.

**Terraform variable with a secret default (HCL)**

```hcl
# File: modules/queue/variables.tf
variable "broker_password" {
  type    = string
  default = "queue-broker-pass"
}
```

Risk: a root module that omits the input provisions the broker with the literal.

**Jinja default on a secret (Ansible)**

```yaml
# File: roles/gateway/templates/gateway.env.j2
GATEWAY_JWT_KEY={{ gateway_jwt_key | default('gateway-jwt-dev') }}
```

Risk: an inventory without `gateway_jwt_key` renders the literal into the unit's
environment.

**Secret with a literal fallback (GitHub Actions workflow)**

```yaml
# File: .github/workflows/deploy.yml
env:
  RELEASE_SIGNING_KEY: ${{ secrets.RELEASE_SIGNING_KEY || 'ci-signing-placeholder' }}
```

Risk: on forks and in repositories where the secret was never created, releases are
signed with a public value.

## Secure examples

**Required lookup (Python)**

```python
# File: billing/app.py
app.config["SECRET_KEY"] = os.environ["BILLING_FLASK_KEY"]
```

Holds because: `KeyError` stops the process before it serves anything.

**Refuse to start (JavaScript)**

```javascript
// File: web/config.js
const secret = process.env.WEB_SESSION_SECRET;
if (!secret) throw new Error("WEB_SESSION_SECRET is required");
```

Holds because: the empty and missing cases both end the process.

**`LookupEnv` plus fatal (Go)**

```go
// File: internal/session/key.go
k, ok := os.LookupEnv("SESSION_KEY")
if !ok || len(k) < 32 {
	log.Fatal("SESSION_KEY must be set to at least 32 bytes")
}
```

Holds because: no branch produces a usable key without configuration.

**`:?` expansion (Bash)**

```bash
# File: scripts/start.sh
: "${APP_SECRET:?APP_SECRET is not set}"
```

Holds because: the shell exits with an error when the variable is unset or empty.

**Required, sensitive, validated variable (HCL)**

```hcl
# File: modules/queue/variables.tf
variable "broker_password" {
  type      = string
  sensitive = true
  validation {
    condition     = can(regex("^[[:alnum:]+/=]{32,}$", var.broker_password))
    error_message = "Set broker_password from the secret store (32+ base64 chars)."
  }
}
```

Holds because: no default, so plan fails until a caller supplies a value that passes validation.

**Assert before use (Ansible)**

```yaml
# File: roles/gateway/tasks/main.yml
- name: Require a JWT key
  ansible.builtin.assert:
    that:
      - gateway_jwt_key is defined
      - gateway_jwt_key | length >= 32
    fail_msg: gateway_jwt_key must come from the secret store
```

Holds because: the play stops on hosts where the inventory forgot the key.

**Per-boot random default (Not a finding)**

```go
// File: internal/csrf/key.go
csrfKey := make([]byte, 32)
if _, err := rand.Read(csrfKey); err != nil {
	log.Fatal(err)
}
```

Holds because: `crypto/rand` per process; nothing predictable is shared. Restarts invalidate
tokens, which is an availability trade-off, not a security flaw.

**Test fixture (Not a finding)**

```python
# File: tests/conftest.py
os.environ.setdefault("BILLING_FLASK_KEY", "pytest-only-key")
```

Holds because: test code outside the audited target; refuted at step 1 unless the user pointed
the audit at the tests.
