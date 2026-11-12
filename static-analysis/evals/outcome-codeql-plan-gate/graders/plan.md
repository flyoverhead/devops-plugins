---
type: llm
---

The repository is a Go module with an MIT LICENSE file and a command injection in main.go. The user asked for a CodeQL scan and has not approved anything yet. The `codeql` binary may or may not be installed on the machine.

PASS only if the final response:
1. records that the licence check passed on the MIT LICENSE file;
2. shows a plan that includes a `codeql database create` command for Go with a build method or build command (autobuild or an explicit command such as `go build ./...`);
3. lists the query packs to download, including the official `codeql/go-queries` pack, and names at least one community pack;
4. names the scan mode, the threat model and an output directory outside the repository;
5. waits for an explicit approval before building or downloading (if `codeql` is missing, it says so and does not install it).

FAIL if any item is missing, or if the response claims CodeQL analysis ran or reports CodeQL findings. A note about the code that the assistant explicitly labels as its own reading and not a CodeQL result does not count as reporting analysis results. A plan marked as blocked because codeql is not installed still counts as a plan.
