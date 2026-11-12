# Worked example: request data into `sh -c` (Go)

## Contents

- The rule
- The test file
- Why it is shaped this way
- Result

The bug: an HTTP handler builds a shell command string from a query or form value. Taint mode
fits because the dangerous thing is a flow, not a call.

## The rule

`go-sh-c-request/go-sh-c-request.yaml`

```yaml
rules:
  - id: go-sh-c-request
    languages: [go]
    severity: HIGH
    message: >-
      HTTP request data reaches the command string of "$SH -c". Pass it as a separate
      argument instead.
    mode: taint
    pattern-sources:
      - pattern: $R.URL.Query().Get(...)
      - pattern: $R.FormValue(...)
      - pattern: $R.PostFormValue(...)
    pattern-sanitizers:
      - pattern: strconv.Atoi(...)
    pattern-sinks:
      - patterns:
          - pattern-either:
              - pattern: exec.Command($SH, "-c", $CMD, ...)
              - pattern: exec.CommandContext($CTX, $SH, "-c", $CMD, ...)
          - metavariable-regex:
              metavariable: $SH
              regex: ^"(sh|bash|/bin/sh|/bin/bash)"$
          - focus-metavariable: $CMD
```

## The test file

`go-sh-c-request/go-sh-c-request.go`, abridged; the real file also has the form, context, nested
and unrelated cases.

```go
func concat(w http.ResponseWriter, r *http.Request) {
	host := r.URL.Query().Get("host")
	// ruleid: go-sh-c-request
	exec.Command("sh", "-c", "ping -c 1 "+host).Run()
}

func argvElement(w http.ResponseWriter, r *http.Request) {
	host := r.URL.Query().Get("host")
	// ok: go-sh-c-request
	exec.Command("ping", "-c", "1", host).Run()
}

func shellScriptArgv(w http.ResponseWriter, r *http.Request) {
	host := r.URL.Query().Get("host")
	// ok: go-sh-c-request
	exec.Command("sh", "-c", `ping -c 1 "$1"`, "sh", host).Run()
}

func sanitised(w http.ResponseWriter, r *http.Request) {
	n, err := strconv.Atoi(r.URL.Query().Get("count"))
	if err != nil {
		return
	}
	// ok: go-sh-c-request
	exec.Command("sh", "-c", "head -n "+strconv.Itoa(n)+" /var/log/app.log").Run()
}
```

Each case is a whole function, because the request value must come from a declared parameter.

## Why it is shaped this way

- The sink names the third argument (`$CMD`) only. Data in the fourth position onward is passed as
  a positional parameter of the script and is not parsed as shell, so those forms stay `ok`.
- `metavariable-regex` on `$SH` limits the sink to real shells, so `exec.Command("ping", "-c", ...)`
  is never a candidate.
- `focus-metavariable: $CMD` puts the finding on the command string, which is the line to fix.
- The first run without the sanitizer reported the `strconv.Itoa(n)` case as a false positive,
  because taint passes through function calls. Declaring `strconv.Atoi(...)` as a sanitizer
  fixed it, and the test case that exposed it stays.

## Result

```text
1/1: ✓ All tests passed
```
