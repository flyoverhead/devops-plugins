---
type: regex
target: {source: file, path: roles/node_exporter/meta/argument_specs.yml}
flags: m
---

(?=[\s\S]*^\s+node_exporter_version:)(?=[\s\S]*^\s+node_exporter_arch:)(?=[\s\S]*^\s+node_exporter_release_url:)(?=[\s\S]*^\s+node_exporter_download_url:)(?=[\s\S]*^\s+node_exporter_binary_path:)(?=[\s\S]*^\s+node_exporter_user:)(?=[\s\S]*^\s+node_exporter_group:)(?=[\s\S]*^\s+node_exporter_listen_address:)(?=[\s\S]*^\s+node_exporter_textfile_dir:)(?=[\s\S]*^\s+node_exporter_collectors_disabled:)(?=[\s\S]*^\s+node_exporter_service_enabled:)
