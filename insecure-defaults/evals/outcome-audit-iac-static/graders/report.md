---
type: llm
---

The fixture has infra/terraform and infra/ansible. Production applies Terraform with prod.tfvars, which sets only region.
- variables.tf: reports_db_password has a literal default and feeds aws_db_instance.password in main.tf; admin_cidr defaults to 0.0.0.0/0 and feeds the security group ingress on port 5432; the instance also sets publicly_accessible = true unconditionally.
- variables.tf: ingest_token has no default, is sensitive and has a validation block. It is the secure counterpart and is not a finding.
- Ansible: roles/metrics_agent/defaults/main.yml sets metrics_agent_validate_certs: false, used by the get_url task that downloads a binary which is then run as a service. group_vars/all.yml does not override it.

PASS only if the final response does all of the following:
1. reports the reports_db_password default as a finding that production uses, because prod.tfvars does not set it;
2. reports the 0.0.0.0/0 admin_cidr default reaching the database ingress (publicly_accessible may be reported alongside it);
3. reports metrics_agent_validate_certs: false disabling TLS verification on the binary download;
4. does not report ingest_token as a finding;
5. gives file:line locations;
6. recommends Terraform variables without defaults plus validation, and/or an Ansible assert, or turning certificate validation on.

FAIL if any item is missing, or if the response says it ran terraform or ansible.
