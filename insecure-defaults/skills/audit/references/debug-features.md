# Debug surfaces left on

**Report when:** a debug mode, profiler, introspection endpoint, stack trace or trace log is on
by default or on when its setting is missing, and it is reachable by someone who should not see
internals, or it writes secrets to output that others read (logs, CI output, `--diff`).

**Skip when:** the feature only changes log verbosity, the debug listener binds to loopback or
a socket only the operator reaches, it sits behind authentication, or the code path exists only
in a development build that production never ships.

Debug features leak in two directions. Outward: an attacker reads stack traces, schema,
profiles or environment dumps. Sideways: secrets land in places with weaker access than the
secret store, such as CI logs, Ansible diff output or shell traces. Both count; name which one
the finding is.

## Contents

- Vulnerable examples (13): Python, JavaScript, Go, Java, Bash, YAML (Ansible, Spring),
  GitHub Actions
- Secure examples (6): loopback listeners, verbosity-only flags, masked output

## Vulnerable examples

**Django debug on by default (Python)**

```python
# File: shop/settings.py
DEBUG = os.environ.get("SHOP_DEBUG", "true") == "true"
```

Risk: an unset variable serves full tracebacks and settings on every error page.

**Traceback returned to the client (Python)**

```python
# File: api/errors.py
return JSONResponse({"error": traceback.format_exc()}, status_code=500)
```

Risk: file paths, library versions and sometimes local variables reach any caller.

**Debug flag that defaults to on (JavaScript)**

```javascript
// File: web/src/config.js
const verbose = process.env.WEB_DEBUG || "true";
```

Risk: verbose mode renders internal error pages; missing configuration turns it on.

**GraphQL introspection and playground in production (JavaScript)**

```javascript
// File: graph/server.js
const server = new ApolloServer({ schema, introspection: true, playground: true });
```

Risk: the full schema, internal mutations included, is one query away.

**Error message concatenated into the response (JavaScript)**

```javascript
// File: api/routes/orders.js
res.status(500).send("lookup failed: " + err.message);
```

Risk: database errors echo table names and query fragments.

**Pprof on the public listener (Go)**

```go
// File: cmd/api/main.go
import _ "net/http/pprof"

func serve() error {
	srv := &http.Server{Addr: ":9090"}
	return srv.ListenAndServe()
}
```

Risk: the blank import registers `/debug/pprof/` on the default mux, which this
server exposes on all interfaces.

**Error text to the client (Go)**

```go
// File: internal/web/handlers.go
http.Error(w, "query: "+err.Error(), http.StatusInternalServerError)
```

Risk: same leak as above, in Go form.

**Spring actuator exposing everything (Java)**

```yaml
# File: src/main/resources/application.yml
management.endpoints.web.exposure.include: "*"
server.error.include-stacktrace: always
```

Risk: `/actuator/env` and `/actuator/heapdump` hand out credentials.

**Xtrace around secrets (Bash)**

```bash
# File: deploy/release.sh
set -euxo pipefail
docker login -u ci -p "$REGISTRY_PASSWORD" registry.example.com
```

Risk: xtrace prints the expanded command, password included, into the job log.

**Key file task that prints its content in diff mode (Ansible)**

```yaml
# File: roles/ledger/tasks/keys.yml
- name: Install master key
  ansible.builtin.copy:
    content: "{{ ledger_master_key }}"
    dest: /etc/ledger/master.key
    mode: "0600"
```

Risk: `--diff` (and `--check --diff`, often recommended in READMEs) prints the new file
content, and a failure prints the task arguments.

**Template carrying a password (Ansible)**

```jinja
# File: roles/ledger/templates/ledger.ini.j2
dsn = postgres://{{ ledger_db.user }}:{{ ledger_db.password }}@{{ ledger_db.host }}/ledger
```

Risk: the task that renders this template shows the password in its diff unless it
sets `diff: false` or `no_log: true`.

**Runner debug forced on (GitHub Actions workflow)**

```yaml
# File: .github/workflows/build.yml
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
```

Risk: verbose logs on public runs; combined with tools that print their env, masked
values can leak in transformed form.

**Secret echoed (GitHub Actions workflow)**

```yaml
# File: .github/workflows/deploy.yml
- run: echo "token is ${{ secrets.DEPLOY_TOKEN }}" > debug.txt
- uses: actions/upload-artifact@v4
  with:
    path: debug.txt
```

Risk: log redaction covers the log, not the artifact anyone with read access downloads.

## Secure examples

**Pprof on a loopback admin listener (Go)**

```go
// File: cmd/api/admin.go
go func() { log.Println(http.ListenAndServe("127.0.0.1:6060", adminMux)) }()
```

Holds because: reachable only from the host.

**Verbosity flag (Python)**

```python
# File: worker/main.py
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")
```

Holds because: changes how much is logged, not what callers see.

**Debug off unless asked (Python)**

```python
# File: shop/settings.py
DEBUG = os.environ.get("SHOP_DEBUG") == "1"
```

Holds because: the missing case is off.

**Secret task without diff output (Ansible)**

```yaml
# File: roles/ledger/tasks/keys.yml
- name: Install master key
  ansible.builtin.copy:
    content: "{{ ledger_master_key }}"
    dest: /etc/ledger/master.key
    mode: "0600"
  no_log: true
  diff: false
```

Holds because: neither the diff nor the failure output contains the value.

**Tracing paused around a secret (Bash)**

```bash
# File: deploy/release.sh
{ set +x; } 2>/dev/null
printf '%s' "$REGISTRY_PASSWORD" | docker login -u ci --password-stdin registry.example.com
```

Holds because: no trace and no password in the process list.

**Generic error body (JavaScript)**

```javascript
// File: api/routes/orders.js
logger.error({ err }, "order lookup failed");
res.status(500).json({ error: "internal error", requestId: req.id });
```

Holds because: details go to the server log; the client gets an id to quote.
