---
type: regex
target: {source: file, path: roles/chrony/molecule/default/molecule.yml}
---

name:\s*["']?\$\{CONTAINER_ENGINE:-docker\}
