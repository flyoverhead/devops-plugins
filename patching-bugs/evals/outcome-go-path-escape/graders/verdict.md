---
type: llm
weight: 2
---

Fixture facts: `target/` is the Go module `example.org/snipvault`. `vault.Save` and `vault.Load` join `Vault.Dir` with the caller's name, so `snipvault save ../../escaped` writes outside `SNIPVAULT_HOME`; nested names such as `go/http.txt` are legitimate. The user started the patching-bugs workflow, allowed building and running the code and tests, and asked for a local commit with no push.

PASS only if the final response does all of the following:
1. says the bug was reproduced by running the built `snipvault` binary (a file written outside the vault directory), not only by reading code;
2. gives a local commit SHA (short or full) for the fix and says nothing was pushed;
3. says a regression test was added that fails on the unpatched code;
4. reports a proof of the patch in which the unpatched build fails, the patched build passes and the reverted tree fails again (any wording of baseline / patched / reverted counts);
5. states a verdict of READY or READY_WITH_CONCERNS (if it is READY_WITH_CONCERNS, any concern counts, for example that the regression stage could not run);
6. names where the report or evidence is kept, under a temporary directory outside `target/`.

FAIL if it says anything was pushed or a pull request was opened, gives NOT_READY or NOT_REPRODUCED, or claims a proof without having run the build.
