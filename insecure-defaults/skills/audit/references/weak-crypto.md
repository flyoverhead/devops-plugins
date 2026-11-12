# Broken or misused crypto

**Report when:** a broken or unsuitable primitive protects a secret, an identity or integrity:
MD5 or SHA-1 for passwords or signatures, DES, RC4, ECB mode, JWT `none` or a symmetric
algorithm where keys are shared, non-cryptographic randomness for tokens, salts or nonces.

**Skip when:** the hash or random number serves a non-security purpose (ETag, cache key,
content-addressed file name, checksum against accidental corruption, load-balancing jitter,
sampling) or the call is a compatibility read path that never creates new protected data.

Most hits in this category are refuted. MD5 is everywhere and usually harmless; the finding
exists only when the trace reaches a password store, a token, a signature or an access decision.
Name that sink in the report, and say plainly when a hit was refuted because its purpose is
cosmetic.

## Contents

- Vulnerable examples (11): Python, JavaScript, Go, Java, Bash
- Secure examples (6): checksums, ETags, cache keys, CSPRNG tokens

## Vulnerable examples

**Unsalted MD5 for stored passwords (Python)**

```python
# File: accounts/models.py
self.password_digest = hashlib.md5(raw_password.encode()).hexdigest()
```

Risk: rainbow tables reverse it in seconds.

**Token from `random` (Python)**

```python
# File: accounts/reset.py
reset_token = "".join(random.choice(ALPHABET) for _ in range(24))
```

Risk: the Mersenne Twister state can be recovered from outputs; tokens become
predictable.

**JWT decode accepting `none` (Python)**

```python
# File: api/auth.py
claims = jwt.decode(raw, key, algorithms=["none", "HS256"])
```

Risk: an unsigned token passes.

**SHA-1 HMAC for webhooks (JavaScript)**

```javascript
// File: hooks/verify.js
const mac = crypto.createHmac("sha1", hookKey).update(body).digest("hex");
```

Risk: SHA-1 HMAC is not yet broken in practice, but report it at LOW with a move to
SHA-256; it is the shape auditors ask about first.

**Legacy cipher factory (JavaScript)**

```javascript
// File: vault-lite/src/box.js
const cipher = crypto.createCipheriv("des-ede3-cbc", key, iv);
```

Risk: 64-bit block cipher, Sweet32 territory for long sessions.

**MD5 as a password hash (Go)**

```go
// File: internal/auth/password.go
sum := md5.Sum([]byte(salt + password))
```

Risk: fast hash, so offline guessing runs at billions per second.

**`math/rand` session token (Go)**

```go
// File: internal/session/id.go
import "math/rand"

func newSessionID() string {
	return fmt.Sprintf("%016x", rand.Int63())
}
```

Risk: seeded predictably; session ids can be guessed.

**RC4 stream (Go)**

```go
// File: internal/legacy/obfuscate.go
c, _ := rc4.NewCipher(key)
```

Risk: biased keystream; no integrity at all.

**ECB mode (Java)**

```java
// File: src/main/java/org/example/crypto/Box.java
Cipher box = Cipher.getInstance("AES/ECB/NoPadding");
```

Risk: identical blocks encrypt identically and leak structure.

**SHA-1 for signatures (Java)**

```java
// File: src/main/java/org/example/sign/Signer.java
Signature s = Signature.getInstance("SHA1withRSA");
MessageDigest d = MessageDigest.getInstance("SHA-1");
```

Risk: SHA-1 collisions are practical; signatures over attacker-chosen data are forgeable.

**`$RANDOM` as a session token (Bash)**

```bash
# File: scripts/issue-session.sh
echo "$RANDOM$RANDOM" > /run/kiosk/session_token
```

Risk: 30 bits from a seeded generator; brute force is instant.

## Secure examples

**MD5 used as an ETag (Go)**

```go
// File: internal/web/static.go
w.Header().Set("ETag", fmt.Sprintf(`"%x"`, md5.Sum(page)))
```

Holds because: the value only drives cache revalidation; refuted at step 4 (no security sink).

**SHA-1 as a cache key (Python)**

```python
# File: render/cache.py
cache_key = hashlib.sha1(template_name.encode()).hexdigest()
```

Holds because: collisions only cost a cache miss.

**Checksum of a downloaded archive (Bash)**

```bash
# File: scripts/fetch.sh
md5sum -c dataset.md5
```

Holds because: detects corruption; the publisher also signs the archive, which is the real check.

**Random jitter (Go)**

```go
// File: internal/retry/backoff.go
delay := base + time.Duration(rand.Int63n(int64(base)))
```

Holds because: `math/rand` is fine for spreading retries.

**Token from `secrets` (Python)**

```python
# File: accounts/reset.py
reset_token = secrets.token_urlsafe(32)
```

Holds because: CSPRNG output with 256 bits.

**Password hashing done right (Go)**

```go
// File: internal/auth/password.go
hash, err := bcrypt.GenerateFromPassword([]byte(password), 12)
```

Holds because: slow, salted, adaptive.
