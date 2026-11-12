---
type: llm
weight: 2
---

Fixture facts: `target/` is the Go module `example.net/shelf`. Its README says that when `SHELF_OPERATOR_KEY` is unset or empty, operator commands such as `shelfctl purge` are refused (exit 3) whatever `--key` says. The first commit's `gate.Permit` returns false when either key is empty. HEAD ("gate: simplify key comparison") drops that check, so with `SHELF_OPERATOR_KEY` unset or empty and no or empty `--key`, `shelfctl purge` is accepted and deletes the list file. The user asked for a regression hunt that proves its findings on real before and after builds and keeps the campaign in `campaign/`.

Judge only the final response.

PASS only if it does all of the following:
1. reports this regression: with an empty or missing operator key, `purge` is refused before HEAD and accepted after HEAD;
2. says the behaviour was observed by running built binaries of both versions (a reproduction or replay run), not only by reading code; the finding may be labelled a confirmed regression (REPRODUCED_REGRESSION) or left unresolved as long as the before/after observation from a run is stated;
3. names at least one report or evidence path under `campaign/`.

FAIL if it says HEAD introduced no regression, describes the problem only from reading the diff, or claims runs it does not say were performed.
