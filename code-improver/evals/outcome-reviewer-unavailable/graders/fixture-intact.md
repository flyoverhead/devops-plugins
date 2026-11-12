---
type: regex
target: {source: file, path: snapcache/disk.go}
---

^package snapcache\n\nimport \(\n\t"os"\n\t"path/filepath"\n\)\n\n// Put stores one rendered snapshot under dir, named after its key\.\nfunc Put\(dir, key string, png \[\]byte\) \{\n\tos\.WriteFile\(filepath\.Join\(dir, key\+"\.png"\), png, 0666\)\n\}\n\n// Get reads a snapshot back; a missing file yields nil\.\nfunc Get\(dir, key string\) \[\]byte \{\n\tb, err := os\.ReadFile\(filepath\.Join\(dir, key\+"\.png"\)\)\n\tif err != nil \{\n\t\treturn nil\n\t\}\n\treturn b\n\}\n$
