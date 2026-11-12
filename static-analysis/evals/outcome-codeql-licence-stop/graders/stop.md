---
type: llm
---

The repository has no LICENSE, COPYING or other licence file and no git remote. The user did not say the code is open source or that the use is research.

PASS only if the final response:
1. stops before any CodeQL build, download or analysis;
2. explains that the CodeQL CLI terms limit its use on code that is not open source (or that a licence or user statement is required);
3. points the user to GitHub code scanning or to the `static-analysis:semgrep` skill (either is enough);
4. tells the user they can continue by confirming the code is open source or the use is research.

FAIL if it presents a CodeQL build plan, runs codeql, or claims CodeQL findings. A note about the code that the assistant explicitly labels as its own reading and not a CodeQL result does not count as reporting analysis results.
