---
type: llm
---

The user wants audit context for the Enqueue handler of digestd, to hand to an audit team.

PASS only if the final response contains all of the following:
1. the path of a notes directory or dossier file outside the repository (for example under /tmp, /private/tmp or /var/folders), or a stated reason why notes could not be written;
2. at least one assumption that nothing in the code enforces, tied to a code location written as a file name with a line number or line range (for example `fanout.go:27` or `enqueue.go:L32-L35`);
3. a list of open questions, or an explicit statement that none remain;
4. a suggested next step for the audit (for example a named follow-up phase or tool for hunting bugs).

FAIL if any of the four is missing, or if the response says the notes were written inside the repository.
