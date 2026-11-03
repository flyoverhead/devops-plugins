---
type: llm
focus: trace
---

PASS if the provider is built on the Plugin Framework: either go.mod requires `github.com/hashicorp/terraform-plugin-framework`, or the Go sources import `github.com/hashicorp/terraform-plugin-framework` packages and the agent reports that module download failed and gives the `go get` / `go mod tidy` commands to finish it. FAIL if the provider uses `terraform-plugin-sdk`, if no Plugin Framework import exists, or if the agent writes dependency versions it never resolved and presents them as verified.
