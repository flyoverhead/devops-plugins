# Shipped credentials

**Report when:** a username and password, API key, token or connection string ships in code,
role defaults, compose files or CI config, and a real service accepts it or is provisioned with
it unless someone overrides it.

**Skip when:** the value is a documented example in docs or a test fixture outside the target,
the service forces a change on first login and cannot be reached before that, or the value is
a reference to a secret store rather than the secret itself.

Shipped credentials are worse than fallback secrets in one way: they are usually the same in
every installation, so a single leaked README or image layer opens all of them. The trace has
to show the credential reaches an authentication check (database login, admin endpoint,
registry) and that deployment does not replace it.

## Contents

- Vulnerable examples (11): Python, JavaScript, Go, Java, YAML (Compose, Helm, Ansible),
  GitHub Actions
- Secure examples (6): store references, forced rotation, fixtures

## Vulnerable examples

**Admin bootstrap with a fixed password (Python)**

```python
# File: inventory/bootstrap.py
User.objects.create_superuser("admin", "ops@example.org", password="Inventory2024")
```

Risk: every fresh database gets the same administrator login.

**Hashing a literal at start-up (Python)**

```python
# File: kiosk/auth.py
DEFAULT_HASH = generate_password_hash("kiosk-operator")
```

Risk: the hash is computed from a known password; the account behind it is open.

**API key literal (JavaScript)**

```javascript
// File: worker/src/geo.js
const apiKey = "gk_live_8f2b77c1d9e04a6a";
```

Risk: anyone with the source calls the upstream API as this service.

**Guest pair in a seed script (JavaScript)**

```javascript
// File: scripts/seed-users.js
await createUser("guest", "guest");
```

Risk: the seed script runs in the production release job.

**DSN with an embedded password (Go)**

```go
// File: internal/store/db.go
const dsn = "postgres://ledger:ledger-pass@db.internal:5432/ledger?sslmode=require"
```

Risk: unconditional; the database account and password are public with the code.

**Bcrypt of a fixed password (Go)**

```go
// File: internal/users/seed.go
hash, _ := bcrypt.GenerateFromPassword([]byte("operator1"), bcrypt.DefaultCost)
```

Risk: the strength of bcrypt is irrelevant when the input is in the repository.

**Properties-style constant (Java)**

```java
// File: src/main/java/org/example/mq/Broker.java
private static final String PASSWORD = "mq-broker-secret";
```

Risk: compiled into every artifact; extracting it takes `strings`.

**Compose database password (YAML)**

```yaml
# File: docker-compose.yml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
```

Risk: when the same compose file starts the production stack, the superuser login is
`postgres/postgres`.

**Helm values with a weak literal (YAML)**

```yaml
# File: charts/search/values.yaml
elastic:
  username: elastic
  password: changeme
```

Risk: the chart renders it into the Secret unless the release overrides it.

**Nested role default left as a placeholder (Ansible)**

```yaml
# File: roles/queue/defaults/main.yml
queue_admin:
  name: admin
  password: REPLACE_ME
```

Risk: unquoted placeholders look like a reminder, but the role renders them as the
real password when the inventory is silent. Check `group_vars/` and `host_vars/` before
deciding.

**Service container and login with literals (GitHub Actions workflow)**

```yaml
# File: .github/workflows/integration.yml
services:
  mysql:
    image: mysql:8.4
    env:
      MYSQL_ROOT_PASSWORD: rootpass
```

Risk: low impact on an ephemeral runner, but the same literal tends to be copied into
staging manifests; report it at LOW unless it is reused elsewhere.

## Secure examples

**Default points at the secret store (Ansible)**

```yaml
# File: roles/queue/defaults/main.yml
queue_admin_password: "{{ lookup('community.hashi_vault.hashi_vault', 'secret=kv/data/queue:admin') }}"
```

Holds because: the repository holds a path, not a value.

**Kubernetes secret reference (YAML)**

```yaml
# File: deploy/search.yaml
env:
  - name: ELASTIC_PASSWORD
    valueFrom:
      secretKeyRef: {name: search-elastic, key: password}
```

Holds because: the credential lives in the cluster, not in the manifest.

**Forced rotation in a setup flow (Go)**

```go
// File: internal/setup/first_run.go
if admin.MustChangePassword {
	return redirectToSetup(w, r)
}
```

Holds because: the generated first-run password only unlocks the setup page, and every other route
redirects there until it is changed.

**Test fixture outside the target (Python)**

```python
# File: tests/factories.py
DEFAULT_TEST_PASSWORD = "factory-pass"
```

Holds because: never packaged; refuted at step 1 unless the audit target is the tests.

**Documentation example (Not a finding)**

```yaml
# File: docs/examples/values.example.yaml
password: "<set-me>"
```

Holds because: an example file nobody deploys. It still deserves a note if a chart copies it.

**Secret from the store (GitHub Actions workflow)**

```yaml
# File: .github/workflows/integration.yml
env:
  MYSQL_ROOT_PASSWORD: ${{ secrets.CI_MYSQL_ROOT }}
```

Holds because: the literal is gone; the secret is masked in logs.
