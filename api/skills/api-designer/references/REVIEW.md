# API review

## Contents

- Dimensions
- Severity tiers
- Report template

## Dimensions

Cite the path and operation for every finding.

| Dimension | Look for |
|---|---|
| Design | Verbs in paths, wrong method semantics, inconsistent naming, missing `operationId`, status-overwrite actions, 201 without `Location` |
| Collections | No pagination, no `maximum` on `limit`, unbounded filters |
| Errors | No shared envelope, inconsistent shapes, missing 401/403/404/409/422/429 |
| Security | No global `security` and no `securitySchemes`, public by omission, password or implicit flows, tokens in query strings, `http` servers |
| Authorization | One scope for everything, server-managed fields in request bodies, no ownership rule on `{id}` operations |
| Resource limits | Unbounded strings or arrays, no 429, no upload size |
| Completeness | Missing summaries, descriptions or examples, unused components, breaking change without a version bump |

## Severity tiers

| Tier | Meaning | Examples |
|---|---|---|
| Critical | Exploitable or consumer-breaking now | Missing authentication, object or function level authorization gaps, secrets in the spec |
| High | Fix before release | Missing pagination, inconsistent errors, undocumented rate limits |
| Medium | Next iteration | Missing `Location`, weak scopes, missing examples |
| Low | Polish | Descriptions, tag order, naming |

## Report template

Print this in the reply. Never write it into the spec. Apply fixes only on a follow-up request.

````markdown
## API review: <spec path>

<title> v<version>, <N> operations

**Verdict:** Changes required | Approved with conditions | Approved

Lint: Spectral <E> errors, <W> warnings | not run: <reason>

### Critical
- [ ] METHOD /path: finding -> fix

### High
- [ ] METHOD /path: finding -> fix

### Medium
- [ ] METHOD /path: finding -> fix

### Low
- [ ] METHOD /path: finding -> fix

### Not verified
- What the spec alone cannot prove, for example implementation behaviour
````

Write each finding as `METHOD /path`, for example `GET /getUsers`. Print "none" under an
empty tier.
