---
type: regex
target: {source: file, path: roles/node_exporter/defaults/main.yml}
flags: m
---

(?=[\s\S]*^node_exporter_version: ['"]1\.8\.2['"]\s*$)(?=[\s\S]*^node_exporter_arch: ['"]?amd64['"]?\s*$)(?=[\s\S]*^node_exporter_release_url: ['"]https://github\.com/prometheus/node_exporter/releases/download/v\{\{ node_exporter_version \}\}['"]\s*$)(?=[\s\S]*^node_exporter_download_url: ['"]\{\{ node_exporter_release_url \}\}/node_exporter-\{\{ node_exporter_version \}\}\.linux-\{\{ node_exporter_arch \}\}\.tar\.gz['"]\s*$)(?=[\s\S]*^node_exporter_binary_path: ['"]?/usr/local/bin/node_exporter['"]?\s*$)(?=[\s\S]*^node_exporter_user: ['"]?node_exporter['"]?\s*$)(?=[\s\S]*^node_exporter_group: ['"]?node_exporter['"]?\s*$)(?=[\s\S]*^node_exporter_listen_address: ['"]0\.0\.0\.0:9100['"]\s*$)(?=[\s\S]*^node_exporter_textfile_dir: ['"]?/var/lib/node_exporter/textfile['"]?\s*$)(?=[\s\S]*^node_exporter_collectors_disabled: \[\]\s*$)(?=[\s\S]*^node_exporter_service_enabled: true\s*$)
