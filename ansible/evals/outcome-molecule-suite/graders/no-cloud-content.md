---
type: regex
target: {source: file, path: roles/chrony/molecule/default/molecule.yml}
match: not_contains
flags: i
---

openstack|vmware|vsphere
