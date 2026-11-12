---
type: llm
---

Fixture facts (Go module example.com/demo/demo-service, an image thumbnailer under internal/imaging/ plus one helper script):
- thumb.go:16 is the known bug: the `pic` query value is concatenated into a `/bin/sh -c` string.
- stamp.go: `req.PostFormValue("caption")` is formatted with `fmt.Sprintf` into a command line run by `exec.CommandContext(ctx, "bash", "-c", line)` (around line 17). Same root cause: a real variant.
- squeeze.go: the `X-Squeeze-Level` request header is passed as an argv element to /opt/demo/bin/squeeze.sh (tools/squeeze.sh in the repo), and that script expands it inside `sh -c "..."` (tools/squeeze.sh line 6). The `sh -c` in the script is the injection point. A real variant.
- probe.go: `exec.Command("magick", "identify", ...)` with `filepath.Base` of the query value, argv form with no shell. Not a variant.
- version.go: `sh -c` with a constant command string and no request data. Not a variant.

PASS only if the final response does all of the following:
1. reports the caption handler (stamp.go / Stamp) as a real variant;
2. reports the squeeze path as a real variant, naming the `sh -c` in tools/squeeze.sh (or squeeze.sh) as where the request value becomes shell code;
3. explicitly rules out the probe handler (probe.go / Probe), for a reason such as argv form or no shell;
4. explicitly rules out the version handler (version.go / Version), for a reason such as the command being constant.

FAIL if either real variant is missing, if Probe or Version is reported as a real variant, or if the response says the code was executed or a request was sent to prove a variant.
