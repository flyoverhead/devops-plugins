# Bug hunt from survivors

## Contents

- [What this job is](#what-this-job-is)
- [1. Where to look](#1-where-to-look)
- [2. Which mutants first](#2-which-mutants-first)
- [3. Investigating one mutant](#3-investigating-one-mutant)
- [4. Writing it up](#4-writing-it-up)
- [Shapes worth knowing](#shapes-worth-knowing)
- [Pace and honesty](#pace-and-honesty)

## What this job is

Survivors mark code nobody tests. That is where bugs hide, but a missing test is a lead, not a
bug. The deliverable is a short list of real bugs, each with a reproduction. It is not a list of
missing tests (that is the analysis job) and not a grade for the suite.

## 1. Where to look

- Run `mewt status` (or read the tool's summary) and note the scope and any inconclusive results
  (timeouts, skipped) before trusting a score.
- Mark sensitive code: authentication, authorization, crypto, parsing, input validation, core
  business logic. Recently changed code with a low score ranks highest. `git log` is not
  pre-approved; ask before running it.
- Pull survivors there: `mewt results --target 'src/auth/**'`, `mewt results --severity high`.
- Order: sensitive code with a low score, sensitive code at any score, core logic with a low score,
  everything else.

## 2. Which mutants first

| When | Mutants |
|---|---|
| now | ER in auth, crypto, parsing or validation; ER on several consecutive lines; IF and IT both surviving on one line of security code; CR on an authorization check |
| next | ER in error paths; IF or IT in compound conditions; CR on a state change; functions with many survivors |
| last | lone operator swaps; utility code; dead code (a cleanup note, not a bug) |

## 3. Investigating one mutant

1. **Read the original code and infer its intent** from names, comments, callers and docs. The
   mutated version is a hypothetical; it says nothing about whether the original is wrong.
2. **Why is it untested?** Dead code, new code, an edge nobody triggers, an error path tested only
   on the happy path, or behaviour that only shows in integration.
3. **Can it be reached** with input an attacker or a user controls? What breaks if the original is
   wrong there? Does it sit on a security boundary?
4. **Ask the question the slug suggests:**
   - ER: does some path report success when it failed?
   - IF / IT: what happens on the untested branch; off-by-one, null, empty?
   - CR: is the statement needed; does its state change really happen?
   - operator swaps: is the comparison or arithmetic right; what happens at the boundary?
5. **Reproduce.** Write a minimal test or script under `$TMPDIR` (or `/tmp`), never in the
   repository, and run it after showing the command and getting a yes. Running it is what makes a
   finding confirmed.

## 4. Writing it up

Per finding, in chat or in a file the user names:

- **Location** (file:line, function)
- **Evidence:** the mutation result and what the manual check showed
- **Issue** and **impact**, with a severity
- **Reproduction:** the test or steps, and its output
- **Fix:** what should change

Classes:

| Class | Meaning | In the bug list |
|---|---|---|
| confirmed | reproduced | yes |
| likely | strong reasoning, not reproduced | yes, marked likely |
| dead code | cannot be reached | no; cleanup advice |
| not a bug | behaves as intended | no |

Close with a summary: campaign scope and figures, count per class, each confirmed bug with location
and severity, and what to look at next.

## Shapes worth knowing

- **ER on consecutive lines:** either the block never runs or the tests tolerate errors. Check
  execution and assertions before deciding which.
- **IF and IT on the same line:** `mewt results --line N` shows both; the branch decision is not
  tested at all.
- **ER in a catch or error return:** which errors can happen there, can an attacker trigger them,
  and does the path leak data or crash?
- **Many mixed survivors in one security file:** review that file's logic by hand for bypasses.

## Pace and honesty

Work one file or area at a time, about the top 10 to 20 mutants, and summarise as you go. If nothing
turns up, report the scope covered and the unresolved cases, and say that this does not prove the
code is bug-free. Correct code with weak tests is a legitimate result.
