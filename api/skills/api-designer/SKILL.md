---
name: api-designer
description: Designs and reviews REST and GraphQL APIs — OpenAPI 3.1 specs with cursor pagination, a shared error envelope, OpenID Connect security schemes, an OWASP-tiered review and Spectral/Redocly linting. Use when asked to design an API, write or review an OpenAPI spec, define endpoints, model a GraphQL schema, or run `--review <spec>`. Not for implementing handlers — use `golang:golang-patterns` or `/golang:scaffold <name> service`.
argument-hint: "[api-name] [style=rest|graphql] or --review <path to openapi file>"
effort: high
paths: ["**/openapi*.yaml", "**/openapi*.yml", "**/*.openapi.json"]
allowed-tools: Bash(npx @stoplight/spectral-cli@6.17.0 *) Bash(npx @redocly/cli@2.65.1 *) Read Write Edit Glob Grep
---

# API designer

Request: $ARGUMENTS

## Mode

- Argument starts with `--review`: review mode. Read-only: never call Edit or Write.
- Anything else: design mode.

## Design mode

Copy this checklist and tick each step as it is done:

```
- [ ] 1. Gather inputs
- [ ] 2. Choose style and resource model
- [ ] 3. Design endpoints, pagination, errors, versioning
- [ ] 4. Design security
- [ ] 5. Write the spec
- [ ] 6. Lint loop
- [ ] 7. Hand off
```

### Inputs

Ask once, in one numbered message, and only for what the request does not already say:

1. Entities, their lifecycle states and who may change each state.
2. Consumers (browser, mobile, other services, third parties).
3. Integrations and compliance constraints.
4. Expected volume, only when it changes the pagination choice.

If the request is enough, skip the questions and list the assumptions at the end. When the
request already names the resources and operations, or the session is non-interactive, state
the assumptions in the output and write the spec instead of stopping to ask.

### Style

REST with OpenAPI 3.1 is the default. Choose GraphQL only for client-driven, graph-shaped
reads; the checks are in [DESIGN.md](references/DESIGN.md). gRPC is out of scope.

### Endpoints

Rules and rationale are in [DESIGN.md](references/DESIGN.md). In short: plural nouns and no
verbs in paths, state transitions as `POST` actions on the entity, every collection
paginated with a capped `limit`, version prefix in the URL.

Defaults, unless the service owner names otherwise:

- Errors use RFC 9457 `application/problem+json`, defined once and shared.
- The spec declares a global top-level `security` requirement; an operation overrides it
  only when it is deliberately public (`security: []`).

### Security

Rules are in [SECURITY.md](references/SECURITY.md).

- Model OpenID Connect as an `oauth2` scheme: Spectral validates operation scopes only for
  `oauth2`. Use `openIdConnect` only when no scopes need validating.
- Authorization code with PKCE for people, client credentials for services.
- Ask for the real provider host and tenant or realm. Never invent them. Treat the provider
  as a choice to confirm, not a default.
- No secrets or real tokens in the spec or its examples.

### Write the spec

1. Start from [SPECIFICATION.md](references/SPECIFICATION.md).
2. Write `openapi.yaml`, or the path the user names. If the file exists, show the diff and
   ask before overwriting.
3. Every operation has `operationId`, `summary`, `tags`, `security` and its possible error
   responses. Every schema property is typed and bounded.

### Lint loop

1. `npx @stoplight/spectral-cli@6.17.0 lint <spec> --ruleset "${CLAUDE_SKILL_DIR}/assets/spectral.yaml"`
   Fix every error and re-run until the exit code is 0.
2. `npx @redocly/cli@2.65.1 lint <spec>`; fix its findings.
3. Report remaining warnings in the summary.

If `npx` cannot run, say so, list the manual checks you did and do not claim the spec is valid.

### Hand off

Summarise endpoints, assumptions and lint output. Implementation goes to
`/golang:scaffold <name> service`, then `golang:golang-patterns`. A Terraform provider for the
API goes to `terraform:provider-creator`.

## Review mode

```
- [ ] 1. Locate the spec
- [ ] 2. Lint
- [ ] 3. Walk the review dimensions
- [ ] 4. Print the report
```

1. Use the path after `--review`. Without one, Glob `**/openapi*.yaml`, `**/openapi*.yml`
   and `**/*.openapi.json`. Several matches: review each and say which. None: say so and stop.
2. Run the lint loop commands above. Record the error and warning counts, or `not run` with
   the reason.
3. Walk the dimensions and tiers in [REVIEW.md](references/REVIEW.md), checking against
   [SECURITY.md](references/SECURITY.md) and [DESIGN.md](references/DESIGN.md).
4. Print the report in the reply using the template in REVIEW.md, never into the spec. Print
   empty tiers as "none". Offer fixes and apply them only when asked.
