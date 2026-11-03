---
type: regex
target: {source: file, path: modules/openstack/instance/versions.tf}
match: not_contains
---

source\s*=\s*"registry\.
