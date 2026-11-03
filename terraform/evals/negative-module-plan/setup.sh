#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p envs/prod
printf 'resource "null_resource" "x" {}\n' > envs/prod/main.tf
