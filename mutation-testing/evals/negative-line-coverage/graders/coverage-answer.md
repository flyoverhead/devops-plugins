---
type: llm
---

The user asked how to get a line-coverage percentage for the Go package pkg/shelf and how to see which lines of life.go never run.

PASS if the final response gives a working Go coverage route: `go test -cover` (or `-coverprofile=<file>`) for the percentage, and `go tool cover -html=<file>` or `go tool cover -func=<file>` (or an equivalent per-line view) for the unexecuted lines. Running the commands is optional.

FAIL if it steers the user to a mutation-testing campaign instead of answering, or gives no command.
