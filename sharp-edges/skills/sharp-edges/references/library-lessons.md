# Lessons from native and widely used libraries

Case studies of interfaces that hurt their users. Use them as yardsticks: when the code under
review wraps or resembles one of these, check whether it inherited the same edge.

### Big-number libraries holding secrets

- **Bites:** general-purpose bignum libraries such as GMP were built for speed, not secrecy.
  Modular exponentiation, comparison, multiplication and reduction run in time that depends on
  the values, so exponent bits leak; the constant-time `sec` functions cover only part of the
  API. CVE-2018-16152, in an IKEv2 implementation, is one public example of the family. Freeing
  a number leaves its limbs in memory, and the export call takes seven parameters, three of them
  about byte order.
- **Spot:** `mpz_*` (or a wrapper) applied to private keys, nonces or shared secrets.
- **Fix:** libsodium, or the constant-time bignum code inside a maintained TLS library.

### Certificate verify callbacks

- **Bites:** the callback's return value is the verdict. A callback added "just for logging"
  that returns `1` accepts every certificate.
- **Spot:** custom verify callbacks; check what they return.
- **Fix:** return the `preverify_ok` value the library passed in, unless a stricter rule fails.

### Return codes and error queues

- **Bites:** in the classic C TLS library success is `1`, not `0`; failures go to a per-thread
  error queue that must be drained, and results of `*_update`/`*_final` calls are often ignored.
- **Spot:** calls whose return value is unused or compared with `0`.
- **Fix:** check every return against the documented success value; clear the queue on error.

### Two random functions with near-identical names

- **Bites:** a secure and a pseudo-random generator differ by a few letters, and the weak one
  returns `1`, `0` or `-1`, all of which look like success to a hurried reader.
- **Spot:** the pseudo variant anywhere near keys or tokens.
- **Fix:** call only the CSPRNG function and check its result.

### Ownership encoded in names

- **Bites:** `get` hands back a copy the caller must free, `get0` a borrowed pointer it must
  not; swap them and you leak or double-free.
- **Spot:** each getter and its matching release.
- **Fix:** wrapper types that own their memory; one convention per API.

### Re-using a cipher context

- **Bites:** re-initialising a context with only a new IV can keep state from the previous
  message, and the rules differ by mode.
- **Spot:** contexts reused across messages without a full reset.
- **Fix:** a fresh context per message, or the high-level AEAD call.

### Pickle

- **Bites:** it looks like a data format and is a code-execution format.
- **Spot:** `pickle.loads` / `load` on anything that crossed a trust boundary.
- **Fix:** JSON or protobuf. An HMAC checked before loading is a fallback, not a fix.

### YAML tags

- **Bites:** the obvious `yaml.load` builds arbitrary objects from tags.
- **Spot:** `load` without `SafeLoader`.
- **Fix:** `yaml.safe_load`.

### Type juggling in string comparison

- **Bites:** in PHP, `strcmp` given an array returns `null`, and `null == 0` is true, so a
  password check passes.
- **Spot:** loose comparison of a comparison function's result.
- **Fix:** strict comparison, and a constant-time compare of hashed values.

## Probe table

Record each probe as a row; a mismatch between the last two columns is a candidate finding.

| Input | Expected | Actual | Class |
|---|---|---|---|
| `verify=False` | refused or loud warning | accepted silently | dangerous default |
| empty password | rejected | accepted | zero-value bypass |
| `alg: none` | rejected | signature skipped | algorithm selection |
| timeout `-1` | rejected | never expires | configuration cliff |

## Safer replacements

- Arithmetic on secret numbers: move from GMP to libsodium or the bignum code shipped inside
  a TLS library.
- Certificate handling: call a maintained high-level wrapper instead of raw OpenSSL functions.
- Untrusted data formats: JSON or protobuf instead of pickle or tag-aware YAML.
- Checking a secret: `hmac.Equal` or `secrets.compare_digest` instead of `==` or `strcmp`.
