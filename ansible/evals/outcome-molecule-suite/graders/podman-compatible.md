---
type: regex
target: {source: file, path: roles/chrony/molecule/default/molecule.yml}
match: not_contains
flags: m
---

cgroupns_mode|^\s+tmpfs:|name:\s*["']?\$\{?MOLECULE_
