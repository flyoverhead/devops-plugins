# Changelog

## 2026-11-12

### Changed

- Agent `api-designer`: Bash is limited to the pinned `npx @stoplight/spectral-cli@6.17.0` and `npx @redocly/cli@2.65.1` commands instead of any command.

## 2026-11-03

Initial release.

- Skill `api-designer`: design mode for REST and GraphQL APIs with a bundled starter OpenAPI 3.1 document and Spectral ruleset, and a read-only review mode with severity tiers.
- Agent `api-designer`: cross-service decisions on versioning, gateway, auth model and contract ownership.
- Hooks: lint OpenAPI files after Edit or Write with Spectral or Redocly; report installed API tooling at session start.
