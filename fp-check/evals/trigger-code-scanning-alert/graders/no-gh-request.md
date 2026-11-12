---
type: llm
---

The user pasted a GitHub code-scanning alert as JSON in the prompt. Everything needed to judge it is in that JSON and in the repository.

PASS if the final response works from the pasted JSON and the code, and does not ask the user to run `gh api`, `gh` or any other command to fetch the alert, and does not say it needs to download or fetch the alert first.

FAIL if the response asks for `gh api` access, asks the user to fetch or re-export the alert, or says it cannot proceed without fetching it from GitHub.
