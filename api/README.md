# api

Design and review APIs: OpenAPI 3.1 specs, REST and GraphQL patterns, and an
OWASP-tiered security review.

```text
/plugin install api@devops
```

## Skills

| Skill | Use when |
|---|---|
| `api-designer` | Designing an API, writing an OpenAPI spec, defining endpoints, modelling a GraphQL schema, or reviewing a spec with `--review <path>` |

Design mode produces a spec that passes the bundled Spectral ruleset and Redocly lint. Review
mode is read-only and prints a report grouped Critical, High, Medium and Low, with a verdict
and a list of what the spec cannot prove. Handler implementation is out of scope; use the
`golang` plugin.

## Agent

`api-designer` is an architect for platforms of several services: versioning, gateway
routing, the auth model and contract ownership. For a single spec or a spec review use the
skill.

## Hooks

- After an Edit or Write of an OpenAPI file, lint it and report findings to the model.
  Spectral is preferred, with the bundled ruleset unless the project has its own
  `.spectral.*` file; Redocly is the fallback.
- At session start, report which API tools are installed.

## Tools

Optional: `spectral`, `redocly`, `swagger-cli`. Missing ones are skipped.
