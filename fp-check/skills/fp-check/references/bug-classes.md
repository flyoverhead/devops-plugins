# Bug classes

Classify in Step 0, then add the questions for that class to S1–S3 (or phases 1–3).

## Contents

- Injection
- Logic and authorisation
- Race and TOCTOU
- Integer and bounds
- Memory corruption
- Cryptography
- Information disclosure
- Denial of service
- Deserialisation
- Secrets, IaC and CI

## Injection

Command, SQL, template, path, header, LDAP, XSS.

- Follow the value from source to sink through every encode, decode, join and format step.
- For XSS, name the output context (HTML body, attribute, script, URL) and the escaping
  applied in that context.
- For paths, check canonicalisation (`filepath.Clean`, `realpath`, symlinks) happens *before*
  the prefix check, not after.
- Ask whether a shell exists in the call path at all. No shell, no shell metacharacters.

## Logic and authorisation

- Compare behaviour against a spec, a doc or the tests; with none, write down the intended
  rule you are assuming.
- Map the state transitions and look for one that skips a check.
- Check every route to the protected action, not just the flagged one.
- A clean scanner run says nothing here.

## Race and TOCTOU

- Size the window; can the attacker widen it?
- Threading model: goroutines per request, worker pool, single event loop, separate processes.
- For files: who controls the path, and can it be swapped between check and use?

## Integer and bounds

- Type at every step, including implicit promotions and casts.
- What the result feeds afterwards: an allocation size, an index, a loop bound, a slice
  expression. Overflow that feeds nothing dangerous is a bug, not a vulnerability.
- Do the algebra in `evidence-rules.md`, "Arithmetic and bounds".

## Memory corruption

- What gets corrupted, and does the attacker control size, offset or contents?
- A usable primitive (write-what-where, controlled free) or only a crash?
- Allocator hardening in play.
- For use-after-free, the full lifetime of the object across owners.

## Cryptography

- Algorithm, key size, mode and parameters against current guidance.
- Randomness from a CSPRNG where secrets or nonces come from.
- Nonce or IV reuse that can actually happen in practice, not only in theory.
- Timing side channels: reachable by the attacker and measurable over the channel they have.

## Information disclosure

- Exactly what leaks and whether it helps an attacker (a token, a path, a version, a stack).
- Uninitialised memory: prove it is uninitialised and reaches output.
- Error paths: does the error text actually reach the attacker?

## Denial of service

- Amplification: attacker cost versus server cost.
- Is the resource reclaimed (timeouts, GC, connection close)?
- Prove the worst-case input, do not estimate it.
- Does a supervisor restart the process, and does that matter for the claim?

## Deserialisation

- Does the attacker control the byte stream?
- Does a gadget chain exist in the loaded classes or types?
- Type allowlists or filters in place.
- The library version and its known behaviour.

## Secrets, IaC and CI

- A secret finding: is it a live credential, a test fixture, an example or a hash? Report the
  location only, value as `<redacted>`.
- IaC: who applies this configuration, and is the flagged value overridden per environment?
- CI: which events run the job, and can a fork or an outside contributor control its inputs?
