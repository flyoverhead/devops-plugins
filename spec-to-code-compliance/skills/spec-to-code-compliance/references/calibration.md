# Three cases that are easy to get wrong

Each case shows the verdict, how it is reached, and the mistake it guards against.

## Implemented, proved by arithmetic

> README, *Sessions*: "An idle session is closed after 30 minutes."

```go
// internal/session/store.go
const idleLimit = 1800 // seconds

func (s *Store) touch(id string) { s.last[id] = s.clock() }

func (s *Store) Valid(id string) bool {
    last, ok := s.last[id]
    return ok && s.clock().Sub(last) < idleLimit*time.Second
}
```

- 1800 seconds is 30 minutes: the bound matches.
- `idleLimit` is a constant; Grep for `idleLimit`, `IDLE`, `SESSION_` finds no env, flag or
  config override.
- Every place that resumes a session calls `Valid` (enumerate the callers); none reads
  `s.last` directly.
- `Valid` rejects at the bound, so the verifier side holds too.

Verdict `implemented`, confidence high. **Mistake:** calling it `absent` because the words
"30 minutes" or "idle timeout" appear nowhere in the code.

## Absent, proved by the search log

> Role README: "The role refuses to run when `mq_admin_password` is empty."

- `defaults/main.yml`: `mq_admin_password: ""`.
- `meta/argument_specs.yml`: the option exists, `type: str`, no `required: true`, no
  `no_log`.
- `tasks/main.yml` has one `assert`, and it checks `ansible_os_family`.
- Search log:

```text
"mq_admin_password" -> tasks/, handlers/, templates/ -> 2 hits, both use the value, neither tests it
"assert|fail" -> tasks/*.yml -> 1 hit, os family only
"length|== ''|is not defined" -> tasks/, meta/ -> 0 hits
meta/main.yml dependencies -> none
```

Verdict `absent`, confidence high: the searches covered argument_specs, every task file,
dependencies and both test idioms. **Mistake:** writing `absent` with no search log; then
nobody can tell "not there" from "not looked for".

## Partial, found by walking every role

> README: "Uploads are limited to 8 MiB for every caller."

```go
// internal/upload/limit.go
func capBody(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.Header.Get("X-Account-Kind") == "system" {
            next.ServeHTTP(w, r) // system accounts stream large archives
            return
        }
        r.Body = http.MaxBytesReader(w, r.Body, 8<<20)
        next.ServeHTTP(w, r)
    })
}
```

- `8<<20` is 8 MiB: the cap is right for ordinary accounts.
- The account kind comes from a header. Who sets it? If an outer gateway sets it and strips
  client copies, that is in config outside the repo: name it as unseen. If nothing strips it,
  any caller can send it.
- Walk both kinds: an ordinary account reaches `MaxBytesReader` (pass); a `system` account
  returns early with no cap (fail).

Verdict `partial`, failing path `internal/upload/limit.go:4-6`. **Mistake:** stopping at the
comment, which explains intent and proves nothing about who can send the header.
