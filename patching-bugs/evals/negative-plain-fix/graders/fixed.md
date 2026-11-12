---
type: llm
---

Fixture facts: `target/` is a Go module where `vault.Save` and `vault.Load` join `Vault.Dir` with a caller-supplied name, so `../x` escapes the vault directory. The user asked for a direct fix plus a unit test, with no report or process.

PASS if the final response says it changed the vault code so that names escaping the vault directory are refused, and that it added a test for that. FAIL if it only explains the bug, asks permission to start a multi-stage reproduce/validate/prove workflow instead of fixing, or claims no change was made.
