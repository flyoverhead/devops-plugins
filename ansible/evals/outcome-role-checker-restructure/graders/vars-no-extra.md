---
type: regex
target: {source: file, path: roles/node_exporter/defaults/main.yml}
match: not_contains
flags: m
---

^(?!(?:node_exporter_version|node_exporter_arch|node_exporter_release_url|node_exporter_download_url|node_exporter_binary_path|node_exporter_user|node_exporter_group|node_exporter_listen_address|node_exporter_textfile_dir|node_exporter_collectors_disabled|node_exporter_service_enabled):)[A-Za-z_][\w]*:
