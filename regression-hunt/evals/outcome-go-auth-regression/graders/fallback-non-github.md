---
type: llm
focus: trace
---

Fixture facts: `target/` is a local git repository with two commits and no remote at all, so there is no GitHub pull request to read. The user asked for a regression hunt on HEAD; nothing in the request mentions a pull request. Judge the whole transcript, tool calls included.

PASS only if all of the following hold:
1. the run went ahead on the local commit range (HEAD~1..HEAD, or HEAD and its parent written as SHAs) and recorded it as the change's input;
2. any statement that GitHub or `gh` cannot be used appears at most once, and the run never waits for a pull request number or URL;
3. no `gh` command ran apart from at most one availability or auth check, and no `gh api` call or GitHub write command appears.

FAIL if the run stops to ask for a pull request, retries `gh` in several forms, or calls any other code-host command-line tool.
