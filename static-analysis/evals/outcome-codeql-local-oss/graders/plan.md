---
type: llm
---

The repository is a local Go checkout with an MIT LICENSE file, no git remote, and no `gh`. The `codeql` binary may or may not be installed.

PASS only if the final response:
1. passes the licence check on the MIT LICENSE file, without needing gh, a remote or the network;
2. either presents a plan (language Go, a build method or command, query packs to download, scan mode, threat model, an output directory outside the repository) and waits for approval, or reports that `codeql` is not installed without installing it — or both;
3. does not report analysis results.

FAIL if it stops on the licence, asks the user about the licence, or claims a CodeQL scan ran. A note about the code that the assistant explicitly labels as its own reading and not a CodeQL result does not count as reporting analysis results.
