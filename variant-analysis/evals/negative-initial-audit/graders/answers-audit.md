---
type: llm
---

The user has no known bug and asked for a first security look at demo-service. That is discovery, not a search for copies of a bug someone already found.

PASS if the final response either discusses security problems it found in the service (for example shell commands built from request values in internal/imaging/), or points the user to a general audit or scanning approach for a codebase with no known findings.

FAIL if the response refuses to look until the user names one known bug location, or if it presents its answer as a per-location variant verdict list derived from a single original bug that the user never reported.
