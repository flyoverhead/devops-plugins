# Records

Three artefacts: the prose file each analyzer writes, the record it returns, and the dossier
the skill builds from the records.

## Prose file

Path: `<notes>/functions/NN-<name>.md`, written by the analyzer and nowhere else. One file per
unit; sections in this order. A section with nothing in it stays, with one line saying so
("No external calls.", "No lasting state touched.").

1. `# <unit>`, then a line: `<path> L<start>-L<end>`.
2. `## Purpose`: what the unit is for in the system, and what would stop working without it.
3. `## Inputs and assumptions`:
   - each parameter with a trust level: `untrusted`, `semi-trusted` or `trusted`, and why;
   - implicit inputs: lasting state, caller identity, environment variables, clock, files;
   - preconditions, each with what establishes it (`path:line`, a function, a setting
     outside the repo) or `nothing found`.
4. `## Outputs and effects`: return values per path, writes, messages sent, external
   interactions, postconditions.
5. `## Walk`: block by block, each block as
   `L<a>-L<b> — <what it does>. Here because <reason>. Assumes <…>. Establishes <…>. Later
   relied on by L<n>.`
6. `## Dependencies`:
   - callees, each tagged `internal`, `external-source-available` or `external-black-box`,
     with what this unit relies on and on which paths it holds;
   - callers, and what each believes this unit enforces;
   - shared state and the other units touching it;
   - how this unit's invariants tie into the rest of the system.
7. `## Open questions`: each one `unclear; need to inspect <X>`.

Corrections: when a later read overturns an earlier line, fix it in place and add
`(corrected: <what changed>)`.

## Returned record

Plain key/value text, the agent's whole final message. It points into the prose file; it does
not summarise it. Keep lines short.

```text
function: <unit name>
file: <repo-relative path> (L<start>-L<end>)
analysisFile: <absolute path of the prose file>
invariants:
  - <claim> | evidence: L<n>
assumptions:
  - <what is taken for granted> | establishedBy: <path:Lnn or func name>
  - <claim> | nothing found
calls:
  - <callee> | internal | propagates: <what this unit relies on it for>
  - <callee> | external-source-available | propagates: <…>
  - <callee> | external-black-box | propagates: <…>
callers:
  - <caller> (<path:line>)
sharedState:
  - <state item, e.g. spool dir, sessions table> | <reads|writes|reads+writes> | <path:Lnn>
openQuestions:
  - unclear; need to inspect <X>
```

- An empty list is written `[]`, never dropped.
- `nothing found` ends the line exactly like that, so that `grep 'nothing found'` lists every
  unenforced assumption across all records.
- An invariant that holds on some paths but not all is not an invariant: it goes under
  `assumptions` with the failing path named.

A refused brief returns only:

```text
refused: <reason, naming the offending path>
```

## Dossier

`<notes>/DOSSIER.md`. Header: repository, commit (or `nogit`), date, focus, units analysed.
Then these sections, in this order:

1. `## State map`: table `| State | Read by | Written by | Invariant implied |`.
2. `## Flows`: numbered, one per way in: `entry → unit → unit → state`, each hop with a line.
3. `## Actor reach`: table `| Actor | Way in | Trust | Reaches |`.
4. `## Complexity hotspots`: unit and lines, with what piles up there.
5. `## Cross-unit invariants`: each citing the two (or more) records it comes from.
6. `## Disagreements`: both record lines quoted, unit names attached, no ruling.
7. `## Unenforced assumptions`: every `nothing found` line verbatim with unit and `path:line`.
8. `## Open questions`: aggregated, each tagged with the unit that raised it.
9. `## Not analysed`: units past the cut, unreliable records, failed dispatches, each with a
   reason.
