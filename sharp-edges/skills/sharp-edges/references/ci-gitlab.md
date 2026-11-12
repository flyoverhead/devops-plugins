# GitLab CI pipelines

Second CI section, after GitHub Actions. A pipeline's interface is its `include:` entries with
their `inputs`, its `rules:` and the variables jobs read. Every entry: **Bites**, **Spot**, **Fix**.

### Rules that fail open

- **Bites:** `if: $CI_COMMIT_BRANCH != "main"` is also true for merge-request and fork
  pipelines, where the branch variable is empty; a trailing `- when: always` runs the job when
  no earlier rule matched; an undefined variable compares as empty, so any `!=` test passes.
- **Spot:** `!=` conditions guarding privileged jobs; catch-all `when: always` at the end of a
  rules list.
- **Fix:** positive matches (`== "main"` plus `$CI_COMMIT_REF_PROTECTED == "true"`), and a final
  `- when: never`.

### Secrets reaching the wrong jobs

- **Bites:** CI/CD variables that are neither protected nor masked are available to every
  branch, including one a developer pushed five minutes ago; `id_tokens` with a broad `aud`, or
  a secret-store role bound to any ref, gives the same reach.
- **Spot:** secret-looking variables used in jobs that run on unprotected refs; `id_tokens`
  audiences and the matching role's bound claims.
- **Fix:** protected and masked variables; roles bound to protected refs and a specific project.

### Mutable references

- **Bites:** `image: tool:latest`, an include pinned to `@~latest` or a branch, or
  `include: remote:` pulls whatever the other side publishes today.
- **Spot:** `:latest`, `@~latest`, branch refs in `include:`, `remote:` includes.
- **Fix:** image digests or fixed tags; includes pinned to a release or commit SHA.

### Security jobs that cannot fail

- **Bites:** `allow_failure: true` on a scanner or signing job, or a `*_DISABLED` variable set
  in the project, keeps the pipeline green without the control.
- **Spot:** `allow_failure: true` on security jobs; variables ending in `_DISABLED`.
- **Fix:** let the job block; review disable switches like code.

### Shell in `script:`

- **Bites:** every Bash edge applies, and `set -x` output lands in job logs readable by every
  developer with access to the project.
- **Spot:** see the Bash reference; additionally `set -x` near secret variables.
- **Fix:** as in the Bash reference; no tracing around secrets.

## Grep set

```bash
grep -rn -E ':latest|@~latest|allow_failure: true|_DISABLED' --include='*.yml' .
grep -rn -E 'include:|remote:|id_tokens:' --include='*.yml' .
```
