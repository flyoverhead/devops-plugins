# API security rules

## Contents

- Authentication
- Authorization
- OWASP API Top 10 (2023) mapping
- Abuse limits and input handling
- Sensitive data

## Authentication

Use an OpenID Connect provider (for example Keycloak, Auth0, Okta, Entra ID or Authentik).
Confirm the choice with the service owner; none is a default. Model it as one `type: oauth2`
scheme, declared once in `components/securitySchemes`, applied globally, with every scope
listed under `scopes`.

```yaml
components:
  securitySchemes:
    oidc:
      type: oauth2
      flows:
        authorizationCode:
          authorizationUrl: https://<idp-host>/<tenant-or-realm>/authorize
          tokenUrl: https://<idp-host>/<tenant-or-realm>/token
          scopes:
            bookings:read: Read bookings
            bookings:write: Create and change bookings
security:
  - oidc: []
```

The URL paths differ per provider; copy them from the provider's discovery document
(`/.well-known/openid-configuration`).

- People use the authorization code flow with PKCE. Services and CI use client credentials.
  Never model the password or implicit flows.
- API keys only for external systems that cannot do OIDC, sent in a header, never in the
  query string.

## Authorization

- Name scopes `<resource>:<action>`. Use one scope per operation group and list it in each
  operation's `security`.
- Object-level authorization is a server duty. Each `{id}` operation description states the
  ownership or tenancy rule and whether a foreign object yields 403 or 404.
- Property-level: use separate read and write schemas with `readOnly` and `writeOnly`. Never
  accept server-managed fields (id, role, admin flag, creator) in request bodies.
- Admin-only operations get their own tag and scope.

## OWASP API Top 10 (2023) mapping

| Risk | Spec-level check |
|---|---|
| API1 Broken object level authorization | Ownership rule on every `{id}` operation; opaque UUID ids |
| API2 Broken authentication | Global `security`; public operations marked `security: []`; 401 documented |
| API3 Broken object property level authorization | Split schemas, `readOnly`/`writeOnly`, `additionalProperties: false` on request bodies |
| API4 Unrestricted resource consumption | `maximum` on `limit`, `maxLength`, `maxItems`, 429 with `Retry-After`, upload size stated |
| API5 Broken function level authorization | Privileged operations have their own scopes; no admin action on a user-scoped path |
| API6 Unrestricted access to sensitive business flows | Abusable flows state a per-actor limit |
| API7 Server side request forgery | URL inputs (`format: uri`) state an allow-list or are dropped |
| API8 Security misconfiguration | Only `https` servers, explicit CORS origins, error bodies free of internals |
| API9 Improper inventory management | One spec per deployed version, deprecated operations marked, no undocumented debug endpoints |
| API10 Unsafe consumption of APIs | Upstream responses are schema-validated before use; note it for integrations |

## Abuse limits and input handling

- Every collection and write operation documents 429 with `Retry-After`. State a numeric
  quota only when the owner supplied one.
- Every string has `maxLength`, or a `pattern` or `format`. Arrays have `maxItems`. Numbers
  have bounds.
- Reject unknown fields on writes.

## Sensitive data

- No secrets or personal data in paths or query strings: they end up in access logs.
- Credential-like properties are `writeOnly: true` and never echoed back.
- Mark personal-data fields in their descriptions so implementers can mask them in logs.
- Keep secrets in a secret manager (for example HashiCorp Vault), never in the spec.
