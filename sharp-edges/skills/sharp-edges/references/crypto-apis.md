# Cryptographic interfaces

Every entry: **Bites** (how a caller gets hurt), **Spot** (what to look for), **Fix** (the
interface change that removes the edge).

### Token picks its own algorithm

- **Bites:** a JWT verifier trusts the `alg` header. `none` skips the signature; an RS256
  public key fed to an HS256 path becomes the HMAC secret anyone can read.
- **Spot:** key callbacks that return a key without checking the token's method;
  `jwt.decode(tok, key)` with no `algorithms=[...]`.
- **Fix:** the key carries its algorithm; the verifier rejects any token whose header disagrees.

### Caller chooses the cipher mode

- **Bites:** `Encrypt(data, key, mode string)` lets someone pass `"ECB"` or plain `"CBC"` with
  no MAC.
- **Spot:** parameters named `mode`, `cipher`, `alg`, `scheme` that accept free strings.
- **Fix:** expose one authenticated construction (AES-GCM, ChaCha20-Poly1305) and no mode knob.

### Hash chosen by string

- **Bites:** `Digest(name string)` or `hashlib.new(cfg.hash)` happily accepts `md5` and `sha1`.
- **Spot:** a hash name read from config or arguments without an allowlist.
- **Fix:** an enum of approved hashes, or no choice at all.

### Key, nonce and IV share one type

- **Bites:** `Seal(key, nonce, plaintext []byte)` compiles with `key` and `nonce` swapped.
- **Spot:** two or more adjacent `[]byte`/`bytes`/`Buffer` parameters with secret meaning.
- **Fix:** distinct types (`type Key [32]byte`, `type Nonce [12]byte`) or a struct argument.

### Caller-supplied nonce

- **Bites:** callers pass a constant or a counter that restarts at zero after a restart; GCM
  with a repeated nonce leaks the authentication key.
- **Spot:** public functions that take a nonce; counters kept in memory only.
- **Fix:** the library draws the nonce from a CSPRNG and prepends it to the ciphertext.

### Secret compared with ordinary equality

- **Bites:** `==`, `bytes.Equal`, `!=` on hex strings or `a == b` in Python stop at the first
  differing byte and leak the MAC through timing.
- **Spot:** comparisons where one side is a MAC, token, API key or password hash.
- **Fix:** `hmac.Equal` / `subtle.ConstantTimeCompare` (Go), `hmac.compare_digest` (Python),
  `crypto.timingSafeEqual` (Node); better, a `Verify` function that hides the comparison.

### Verdict as a bare boolean

- **Bites:** `Verify(...) bool` with `true` returned on an internal error, or an `int` where
  both `0` and `1` can mean success depending on the call.
- **Spot:** verify/check functions with no error return; mixed return conventions in one API.
- **Fix:** return `error` (nil only on proven validity) or a result type that cannot be
  mistaken for success.

### Decrypt without authentication

- **Bites:** a public `DecryptCBC` that strips padding before any MAC check is a padding oracle.
- **Spot:** decrypt helpers exported separately from verification.
- **Fix:** only export an open-and-verify call; verify the tag before touching padding.

### Errors that tell failures apart

- **Bites:** "bad padding" vs "bad MAC", or a faster path for one of them, tells an attacker
  which guess was closer.
- **Spot:** distinct error strings or early returns in the decrypt path.
- **Fix:** one opaque error for every failure, reached after the same amount of work.

### Plain hash as a key derivation

- **Bites:** `key := sha256(password)` gives a fast-to-brute-force key with no salt.
- **Spot:** keys built from a password or shared secret by one hash call.
- **Fix:** HKDF for high-entropy input; Argon2id or scrypt for passwords.

### Password storage helpers

- **Bites:** `StorePassword` that defaults to SHA-256, takes an optional salt, or exposes a
  cost of `0`.
- **Spot:** password helpers with algorithm, salt or cost parameters.
- **Fix:** bcrypt, scrypt or Argon2id with a fixed minimum cost and an internal salt.
