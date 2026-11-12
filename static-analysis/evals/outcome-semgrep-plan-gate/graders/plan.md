---
type: llm
---

The repository is a small Go module with a command injection in main.go. The user asked for a Semgrep scan and has not approved anything yet.

PASS only if the final response presents a scan plan and stops for approval, and the plan:
1. names Go as a detected language;
2. pre-selects the public registry packs `p/default`, `p/secrets` and a Go pack such as `p/golang` (or `p/go`);
3. shows any other registry pack and any third-party rule repository only as unselected opt-ins;
4. lists what will be downloaded (registry packs, and clones only if opted in);
5. states `--metrics=off` or that no code leaves the machine;
6. puts the output directory outside the repository (for example under `$TMPDIR` or /tmp);
7. asks the user to approve before scanning.

FAIL if any item is missing, if the response reports scan results, or if it mentions GitLab analyzer images or rules.
