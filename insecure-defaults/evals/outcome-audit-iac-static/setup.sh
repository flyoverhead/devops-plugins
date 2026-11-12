#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p infra/terraform infra/ansible/roles/metrics_agent/{defaults,tasks} infra/ansible/group_vars
cat > infra/terraform/versions.tf <<'HCL'
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}
HCL
cat > infra/terraform/variables.tf <<'HCL'
variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "reports_db_password" {
  type    = string
  default = "reports-temp-pass"
}

variable "admin_cidr" {
  type    = string
  default = "0.0.0.0/0"
}

variable "ingest_token" {
  type      = string
  sensitive = true

  validation {
    condition     = length(var.ingest_token) >= 32
    error_message = "ingest_token must be at least 32 characters."
  }
}
HCL
cat > infra/terraform/main.tf <<'HCL'
resource "aws_security_group" "reports" {
  name = "reports-db"

  ingress {
    description = "Postgres from admin network"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
}

resource "aws_db_instance" "reports" {
  identifier             = "reports"
  engine                 = "postgres"
  instance_class         = "db.t4g.small"
  allocated_storage      = 20
  username               = "reports"
  password               = var.reports_db_password
  publicly_accessible    = true
  vpc_security_group_ids = [aws_security_group.reports.id]
  skip_final_snapshot    = true
}

resource "aws_ssm_parameter" "ingest_token" {
  name  = "/reports/ingest-token"
  type  = "SecureString"
  value = var.ingest_token
}
HCL
cat > infra/terraform/prod.tfvars <<'HCL'
region = "eu-west-1"
HCL
cat > infra/ansible/group_vars/all.yml <<'YAML'
---
metrics_agent_version: "2.8.1"
YAML
cat > infra/ansible/roles/metrics_agent/defaults/main.yml <<'YAML'
---
metrics_agent_version: "2.8.0"
metrics_agent_download_url: "https://downloads.example.net/metrics-agent/{{ metrics_agent_version }}/metrics-agent-linux-amd64"
metrics_agent_validate_certs: false
YAML
cat > infra/ansible/roles/metrics_agent/tasks/main.yml <<'YAML'
---
- name: Download metrics agent binary
  ansible.builtin.get_url:
    url: "{{ metrics_agent_download_url }}"
    dest: /usr/local/bin/metrics-agent
    mode: "0755"
    validate_certs: "{{ metrics_agent_validate_certs }}"

- name: Install metrics agent unit
  ansible.builtin.copy:
    dest: /etc/systemd/system/metrics-agent.service
    mode: "0644"
    content: |
      [Unit]
      Description=metrics agent
      [Service]
      ExecStart=/usr/local/bin/metrics-agent
      [Install]
      WantedBy=multi-user.target
YAML
cat > infra/ansible/site.yml <<'YAML'
---
- name: Reporting hosts
  hosts: reports
  become: true
  roles:
    - metrics_agent
YAML
git add -A && git commit -q -m "reports infra"
