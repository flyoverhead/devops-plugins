---
type: regex
target: {source: file, path: roles/chrony/tasks/install.yml}
flags: im
---

^-[^\n]*\n(?=(?:[ \t][^\n]*\n?)*?[ \t][^\n]*chronyd --version)(?=(?:[ \t][^\n]*\n?)*?[ \t]+check_mode: false)
