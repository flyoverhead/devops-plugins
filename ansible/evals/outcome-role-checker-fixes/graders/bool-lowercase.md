---
type: regex
target: {source: file, path: roles/chrony/tasks/main.yml}
match: not_contains
flags: m
---

(?::|^\s*-)\s+(?!(?:true|false)\s*(?:#.*)?$)([Tt][Rr][Uu][Ee]|[Ff][Aa][Ll][Ss][Ee]|[Yy][Ee][Ss]|[Nn][Oo]|[Oo][Nn]|[Oo][Ff][Ff])\s*(?:#.*)?$
