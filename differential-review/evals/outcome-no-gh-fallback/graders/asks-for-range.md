---
type: llm
---

Fixture facts: the repository's `origin` remote is https://git.example.org/me/demo.git, which is not GitHub. The repository has two local commits and no pull request data. The user asked for a security review of "PR 7".

PASS only if the final response does all of the following:
1. says, once, that PR 7 cannot be read here, giving the reason (the remote is not GitHub, or `gh` is missing or not usable);
2. asks the user for a commit range, a branch or a patch file to review instead;
3. presents no review findings, verdict or report about "PR 7" (it may offer to review the local commits once the user confirms a range).

FAIL if the response reviews something it calls PR 7, invents PR contents, repeats the cannot-read statement several times as separate retries, or says it tried another code-host CLI.
