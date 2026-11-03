# API design rules

## Contents

- Resources and URLs
- Non-CRUD actions
- Collections
- Errors
- Versioning and deprecation
- Idempotency
- GraphQL

## Resources and URLs

- Paths use plural nouns, lowercase, kebab-case segments: `/bookings`, `/room-types`. No verbs.
- Nest at most one level (`/rooms/{id}/bookings`). Deeper relations become top-level
  resources with a filter query parameter (`/bookings?roomId=...`).
- Pick one JSON property naming style per spec, camelCase or snake_case, and keep it. Query
  and path parameter names follow the same style.
- Timestamps are RFC 3339 `date-time` in UTC.
- `operationId` is unique and verb-first camelCase: `listBookings`, `confirmBooking`.
- Every operation has `summary`, `tags` and `security`. An explicit `security: []` marks a
  deliberately public operation.

| Method | Use | Success |
|---|---|---|
| GET | Read, no side effects | 200 |
| POST | Create | 201 with `Location` |
| POST | Accepted for async work | 202 |
| POST | Action with a result | 200 |
| PUT | Full replace, idempotent | 200 or 204 |
| PATCH | Partial update, `application/merge-patch+json` (JSON Merge Patch) | 200 |
| DELETE | Remove | 204 |

A repeated DELETE returns 204 or 404; the spec states which.

Document these errors on every operation where they can occur: 400, 401, 403, 404, 409
(state conflict), 422 (semantic validation), 429, and one shared 5xx response.

## Non-CRUD actions

- Model a transition as `POST /{collection}/{id}/{action}`, for example
  `POST /bookings/{id}/cancel`. Do not overwrite a status field through PUT or PATCH.
- Return the updated entity with 200. Return 409 when the current state forbids the transition.
- Describe the state machine (states and allowed transitions) in the entity schema description.

## Collections

- Every collection is paginated.
- Default is cursor pagination: query parameters `limit` and `cursor`; the response has
  `items` and `nextCursor`, which is `null` on the last page. Use page/size only for small,
  stable sets.
- `limit` has a schema `maximum`.
- Filters are explicit, named query parameters. Never accept an expression string that is
  passed to a datastore.
- Sorting uses a single `sort` parameter: an enum of allowed fields, a leading `-` for
  descending.

## Errors

- Define one error envelope once in `components/schemas` and return it through shared
  `components/responses`.
- The default is RFC 9457 `application/problem+json` with `type`, `title`, `status`,
  `detail`, `instance`, plus an `errors[]` extension for field-level validation. If the
  service owner names another envelope, use it consistently instead.
- Never expose stack traces, SQL, internal hostnames or library versions.

## Versioning and deprecation

- Version in the URL prefix (`/v1`). Bump only on a breaking change.
- Non-breaking: a new optional field, a new endpoint, a new response enum value.
- Breaking: removing or renaming anything, tightening validation, changing a type.
- Deprecate with `deprecated: true`, the `Deprecation` and `Sunset` response headers and a
  changelog entry naming the replacement. Remove only in the next major version.

## Idempotency

- State-changing POSTs that clients retry (create, payment-like, provisioning) accept an
  `Idempotency-Key` header, declared once as a reusable parameter.
- The server stores the first result per key and replays it.
- Document 409 or 422 for a key reused with a different body.

## GraphQL

Use GraphQL only when clients drive graph-shaped reads. The deliverable is SDL, not OpenAPI.

- Mutations return typed payloads holding the result and a list of user errors.
- No raw datastore filters in arguments.
- Pagination uses Relay-style connections.
- Enforce query depth and complexity limits.
- In production use persisted queries or an allow-list, and turn introspection off on
  public endpoints.
- Authorize at field level in resolvers, not only at the gateway.
- Evolve with `@deprecated(reason:)` instead of schema versions.
