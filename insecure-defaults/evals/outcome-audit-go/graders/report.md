---
type: llm
---

The fixture is a small Go HTTP API (main.go). newCookieSigner() reads SHOPFRONT_COOKIE_SECRET and, if it is empty, swaps in a hardcoded string (lines 21-24). That secret is the HMAC-SHA256 key of cookieSigner: seal() signs the "cart" cookie issued by the cart handler, and open() checks it with hmac.Equal in the orders handler, which then trusts the owner inside the cookie. deploy/values.yaml supplies only the image and LOG_LEVEL, so a deployment from it uses the hardcoded string. The catalog handler hashes a static JSON body with md5.Sum only to produce an ETag header.

PASS only if the final response does all of the following:
1. reports the cookie-secret fallback as a finding with a main.go location;
2. names the HMAC signing or verification of the cookie (seal, open, hmac.New, hmac.Equal, cookieSigner, or the cart/orders handlers) as where the secret is enforced;
3. says the deploy values do not set SHOPFRONT_COOKIE_SECRET, so production would run on the fallback (CRITICAL or HIGH, or equivalent wording);
4. does not report the MD5 ETag as a finding (calling it refuted or not a finding is fine);
5. recommends failing at startup when the secret is unset, or loading it from a secret manager;
6. has a coverage or limits section saying what was searched and what was not.

Extra findings (for example cookie Secure/SameSite flags) and design notes are acceptable and do not affect the verdict. Showing the fallback value redacted is expected.

FAIL if any numbered item is missing or if the MD5 ETag appears among the confirmed findings.
