# Authentication, sessions and authorisation

Every entry: **Bites**, **Spot**, **Fix**.

## Contents

- Credentials: password comparison, long passwords, check order
- Sessions and tokens: fixation, weak generation, timeouts, OTP lifetime, reuse
- Authorisation: accumulating roles, missing checks, object references
- Second factor and recovery: optional MFA, recovery codes

## Credentials

### Password comparison holes

- **Bites:** a user created without a password has an empty stored hash, and the login code
  compares it with the empty input and lets them in; or the compare is not constant-time.
- **Spot:** `stored == hash(input)` with no guard for an empty `stored`.
- **Fix:** refuse empty passwords at creation and at login; compare with a constant-time call.

### Long passwords cut short

- **Bites:** bcrypt reads only the first 72 bytes, so two passwords with a shared prefix match;
  some libraries truncate silently, others error.
- **Spot:** bcrypt without a length check; any `[:N]` applied to a password.
- **Fix:** reject over-long input with an error, or pre-hash with a keyed hash before bcrypt.

### Checks in the wrong order

- **Bites:** "unknown user" returns faster or differently than "wrong password", or the lockout
  counter is read before the password check and reveals which accounts exist.
- **Spot:** early returns before the password hash runs; distinct error messages.
- **Fix:** do the same work for every path and return one generic failure.

## Sessions and tokens

### Session survives login

- **Bites:** the session ID set before login stays valid after it, so a planted ID becomes an
  authenticated one.
- **Spot:** a login handler that writes `user_id` into the existing session.
- **Fix:** issue a fresh ID on every privilege change; make the old one invalid.

### Guessable tokens

- **Bites:** `math/rand`, `random.random`, `Math.random`, timestamps or short IDs used for reset
  links, API keys or session IDs.
- **Spot:** token helpers and the randomness source they call.
- **Fix:** `crypto/rand`, `secrets`, `crypto.randomBytes`; at least 128 bits.

### Timeouts with sentinel meanings

- **Bites:** `SessionTTL: 0` means "never expires"; `-1` overflows into a far future;
  an absent setting falls back to no expiry.
- **Spot:** duration fields whose zero value skips the expiry check.
- **Fix:** validate both bounds; make "no expiry" a separate, explicit option, if it exists at all.

### One-time codes with no lifetime

- **Bites:** an OTP lifetime of `0` or a missing upper bound lets any old code through.
- **Spot:** lifetime and window parameters without a minimum and maximum.
- **Fix:** fixed bounds in code; reject configuration outside them.

### One-time tokens used twice

- **Bites:** reset or invite tokens stay valid after use, so a leaked link keeps working.
- **Spot:** a verify path that never marks the token consumed.
- **Fix:** consume on first use, atomically with the action it authorises.

## Authorisation

### Grants that only grow

- **Bites:** roles merge by appending, so a user moved out of `admin` keeps it; defaults and
  overrides are unioned instead of replaced.
- **Spot:** `append(roles, ...)`, list merges of permission sets, no revoke path.
- **Fix:** compute effective permissions from scratch; make removal a first-class operation.

### Authenticated but not authorised

- **Bites:** middleware proves who the caller is, and the handler never asks whether they may
  do this.
- **Spot:** handlers that use the user only for logging; routes registered outside the authz
  wrapper.
- **Fix:** deny by default at the router; every route declares the permission it needs.

### Object IDs taken on trust

- **Bites:** `GET /invoices/{id}` loads any invoice by ID without checking the owner.
- **Spot:** lookups by caller-supplied ID with no owner or tenant filter.
- **Fix:** repository methods that require the principal (`InvoiceFor(user, id)`).

## Second factor and recovery

### Second factor that can be skipped

- **Bites:** an `mfa_required` flag defaulting off, a "remember this device" path without
  binding, or an SMS fallback weaker than the primary factor.
- **Spot:** branches that complete login before the second step; per-user opt-out fields.
- **Fix:** MFA state lives server-side; the session is not authenticated until every step passes.

### Recovery codes that never run out

- **Bites:** codes without an attempt limit, an expiry or single use.
- **Spot:** recovery verification without a counter or a delete-on-use.
- **Fix:** hashed single-use codes, rate-limited, regenerated as a set.
