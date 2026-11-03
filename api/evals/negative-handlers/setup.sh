#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p api
cat > api/openapi.yaml <<'YAML'
openapi: 3.1.0
info: {title: Users, version: 0.1.0}
paths:
  /getUsers:
    get:
      responses:
        '200':
          description: all users
          content:
            application/json:
              schema: {type: array, items: {type: object}}
YAML
git add -A && git commit -q -m init
