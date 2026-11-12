# Triage

Every candidate is presumed innocent. The job is to find the reason it is *not* the bug;
only when none survives is it a variant.

## Contents

- [Arguing against a candidate](#arguing-against-a-candidate)
- [Edge cases to try on every candidate](#edge-cases-to-try-on-every-candidate)
- [Verdict rules](#verdict-rules)
- [Severity and confidence](#severity-and-confidence)
- [Grouping false positives](#grouping-false-positives)
- [What only execution could settle](#what-only-execution-could-settle)

## Arguing against a candidate

For each `path:line`, read the enclosing function or task, then its callers, and look for:

1. **A guard** on the path: allow-list, regexp match with anchors, early return, auth
   middleware on the route.
2. **A sanitiser**: `filepath.Base` for a path, `shlex.quote` / `printf %q` for a shell word,
   HTML escaping for markup.
3. **A safe API**: argv form instead of a shell string, bound SQL parameters, `command:`
   with `argv:` in Ansible.
4. **A type constraint**: the value is parsed to an int, an enum, a UUID before it arrives.
5. **The caller set**: every caller passes a constant, or only code with no attacker input
   reaches it.

Write down which of the five you checked and what you found. A candidate dismissed without
naming the reason is not triaged.

## Edge cases to try on every candidate

- both sides of a comparison empty or `nil` at once (`user.Org == resource.Org` with two
  empty strings authorises everyone);
- a function named `deny`/`block`/`isValid` whose `true` means the opposite at this site;
- the anonymous caller: no token, no session, no header;
- empty string versus missing key versus `null`;
- zero, negative and maximum values for lengths and counts;
- empty collections: an empty allow-list that allows everything;
- the boundary of a type (`int32` overflow, a 256-byte name into a 255-byte field).

## Verdict rules

| Situation | Verdict |
|---|---|
| Reachable, attacker controls the value, protection missing | confirmed variant |
| Reachable and controllable, but a *different* protection is present | false positive, recorded with that protection |
| Unprotected, no caller today | confirmed variant, lower severity; say what would make it reachable |
| Constant input, argv form, dead code | false positive, recorded with the reason |
| Cannot decide without running it | "worth a manual check" with the exact command |

"Nobody calls it today" never refutes a variant on its own: the next caller will not read
this report. Informational findings stay in the report; nothing is dropped for being minor.

## Severity and confidence

Two separate fields. Severity is how bad it is if real; confidence is how sure you are it
is real.

| Severity | Meaning |
|---|---|
| critical | unauthenticated code execution, credential theft, whole-system takeover |
| high | code execution or data access needing low privilege or one user action |
| medium | needs significant privilege, a narrow precondition or a chained bug |
| low | hardening gap, limited impact |
| info | worth knowing, no direct impact today |

| Confidence | Meaning |
|---|---|
| high | source, path and sink all read; no protection found anywhere on the path |
| medium | one hop inferred (a caller in another repo, a value from config you could not see) |
| low | pattern match with the path only partly read |

## Grouping false positives

Group dismissed candidates by reason and count them: "argv form, no shell (4)", "constant
command (2)", "behind `requireAdmin` middleware (3)". Each group is a `pattern-not` waiting
to be added to the regression guard.

## What only execution could settle

Some questions are dynamic: whether a reverse proxy strips a header, whether a package
installs a script at the path the code calls, what a templated value expands to at deploy
time. Do not run anything to find out. Put the location, the open question and the exact
command a human would run in the "Worth a manual check" table.
