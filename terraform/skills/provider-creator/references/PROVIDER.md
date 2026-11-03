# Provider skeleton

The sample is a provider named `inventory` with one resource, `inventory_host`, owner placeholder
`example`, endpoint `https://inventory.example.internal/api/v1` and the environment variables
`INVENTORY_ENDPOINT` and `INVENTORY_TOKEN`. Substitute the real names; when the owner is unknown,
keep `example` and tell the user.

## Contents

- Layout
- go.mod
- main.go
- provider.go
- Naming
- Examples for tfplugindocs

## Layout

```text
terraform-provider-inventory/
├── main.go
├── go.mod  go.sum
├── internal/
│   ├── client/            # HTTP client, no Terraform imports
│   └── provider/          # provider.go, host_resource.go, host_data_source.go, host_model.go, tests
├── examples/              # provider/, resources/, data-sources/
├── docs/                  # generated, committed
├── .github/workflows/     # test.yml, release.yml
├── .goreleaser.yml  .golangci.yml  GNUmakefile
├── terraform-registry-manifest.json
└── CHANGELOG.md  README.md  LICENSE
```

The repository root is the provider repository. Use a `terraform-provider-<name>/` subdirectory
only when the working directory already holds another project. There is no `cmd/` directory and no
vendoring.

## go.mod

Module path: `github.com/example/terraform-provider-inventory`. Write it before any Go file, then
resolve the dependencies from the module proxy rather than from memory:

```bash
go mod init github.com/example/terraform-provider-inventory
go get github.com/hashicorp/terraform-plugin-framework@latest
go get github.com/hashicorp/terraform-plugin-go@latest
go get github.com/hashicorp/terraform-plugin-testing@latest
go get -tool github.com/hashicorp/terraform-plugin-docs/cmd/tfplugindocs@latest
go mod tidy
```

The result lists the three libraries under `require` and the docs generator under a `tool`
directive. `go get` may raise the `go` directive; keep what it writes. Optional libraries
(`terraform-plugin-framework-validators`, `terraform-plugin-framework-timeouts`) are added when a
schema needs them. Never import `github.com/hashicorp/terraform-plugin-sdk/v2` in a new provider.

## main.go

**`main.go`**

```go
package main

import (
	"context"
	"flag"
	"log"

	"github.com/hashicorp/terraform-plugin-framework/providerserver"

	"github.com/example/terraform-provider-inventory/internal/provider"
)

//go:generate terraform fmt -recursive ./examples/
//go:generate go tool tfplugindocs generate --provider-name inventory

var version = "dev"

func main() {
	var debug bool
	flag.BoolVar(&debug, "debug", false, "serve with debugger support")
	flag.Parse()

	err := providerserver.Serve(context.Background(), provider.New(version), providerserver.ServeOpts{
		Address: "registry.terraform.io/example/inventory",
		Debug:   debug,
	})
	if err != nil {
		log.Fatal(err)
	}
}
```

`version` is set by goreleaser through `-X main.version=...`. `log.Fatal` is acceptable in `main`
only. `Address` must equal the registry address `registry.terraform.io/<owner>/<name>`.

## provider.go

The type implements `provider.Provider`. `New(version)` returns a constructor. `Configure` runs in
this order:

1. read the configuration into a model;
2. fail on unknown values with a clear message (the provider cannot configure itself from a value
   that is not known yet);
3. take the environment value only when the attribute is null;
4. add an attribute-level error for each value that is still missing;
5. build one client with a 30 second timeout;
6. hand it to both `ResourceData` and `DataSourceData`.

**`internal/provider/provider.go`**

```go
package provider

import (
	"context"
	"os"
	"time"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/path"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	pschema "github.com/hashicorp/terraform-plugin-framework/provider/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"github.com/example/terraform-provider-inventory/internal/client"
)

var _ provider.Provider = (*inventoryProvider)(nil)

type inventoryProvider struct {
	version string
}

type providerModel struct {
	BaseURL    types.String `tfsdk:"endpoint"`
	Credential types.String `tfsdk:"token"`
}

func New(version string) func() provider.Provider {
	return func() provider.Provider { return &inventoryProvider{version: version} }
}

func (p *inventoryProvider) Metadata(_ context.Context, _ provider.MetadataRequest, resp *provider.MetadataResponse) {
	resp.TypeName = "inventory"
	resp.Version = p.version
}

func (p *inventoryProvider) Schema(_ context.Context, _ provider.SchemaRequest, resp *provider.SchemaResponse) {
	resp.Schema = pschema.Schema{
		Description: "Manage hosts in an inventory service.",
		Attributes: map[string]pschema.Attribute{
			"endpoint": pschema.StringAttribute{
				Optional:    true,
				Description: "Base URL of the API. Falls back to INVENTORY_ENDPOINT.",
			},
			"token": pschema.StringAttribute{
				Optional:    true,
				Sensitive:   true,
				Description: "Bearer token. Falls back to INVENTORY_TOKEN.",
			},
		},
	}
}

func (p *inventoryProvider) Configure(ctx context.Context, req provider.ConfigureRequest, resp *provider.ConfigureResponse) {
	var conf providerModel
	resp.Diagnostics.Append(req.Config.Get(ctx, &conf)...)
	if resp.Diagnostics.HasError() {
		return
	}

	if conf.BaseURL.IsUnknown() {
		resp.Diagnostics.AddAttributeError(path.Root("endpoint"), "Unknown endpoint",
			"The endpoint is not known yet. Set it to a static value or to a value known at plan time.")
	}
	if conf.Credential.IsUnknown() {
		resp.Diagnostics.AddAttributeError(path.Root("token"), "Unknown token",
			"The token is not known yet. Set it to a static value or use INVENTORY_TOKEN.")
	}
	if resp.Diagnostics.HasError() {
		return
	}

	var endpoint, token string
	if conf.BaseURL.IsNull() {
		endpoint = os.Getenv("INVENTORY_ENDPOINT")
	} else {
		endpoint = conf.BaseURL.ValueString()
	}
	if conf.Credential.IsNull() {
		token = os.Getenv("INVENTORY_TOKEN")
	} else {
		token = conf.Credential.ValueString()
	}

	if endpoint == "" {
		resp.Diagnostics.AddAttributeError(path.Root("endpoint"), "Missing endpoint",
			"Set the endpoint attribute or the INVENTORY_ENDPOINT environment variable.")
	}
	if token == "" {
		resp.Diagnostics.AddAttributeError(path.Root("token"), "Missing token",
			"Set the token attribute or the INVENTORY_TOKEN environment variable.")
	}
	if resp.Diagnostics.HasError() {
		return
	}

	c := client.New(endpoint, token, 30*time.Second)
	resp.ResourceData = c
	resp.DataSourceData = c
}

func (p *inventoryProvider) Resources(_ context.Context) []func() resource.Resource {
	return []func() resource.Resource{NewHostResource}
}

func (p *inventoryProvider) DataSources(_ context.Context) []func() datasource.DataSource {
	return []func() datasource.DataSource{NewHostDataSource}
}
```

## Naming

| Item | Form | Example |
|---|---|---|
| Provider type | short, lowercase | `inventory` |
| Resource and data source type | `<provider>_<noun>`, singular | `inventory_host` |
| Go types | `<noun>Resource`, `<noun>DataSource`, `<noun>Model` | `hostResource`, `hostModel` |
| Constructors | `New<Noun>Resource`, `New<Noun>DataSource` | `NewHostResource` |
| Files | `<noun>_resource.go`, `<noun>_data_source.go`, `<noun>_model.go` | `host_resource.go` |
| Attributes | snake_case, with the unit in the name | `timeout_seconds` |

## Examples for tfplugindocs

```text
examples/provider/provider.tf
examples/resources/inventory_host/resource.tf
examples/resources/inventory_host/import.sh
examples/data-sources/inventory_host/data-source.tf
```

`provider.tf` declares `required_providers` with the full registry address:

```hcl
terraform {
  required_providers {
    inventory = {
      source = "registry.terraform.io/example/inventory"
    }
  }
}

provider "inventory" {
  endpoint = "https://inventory.example.internal/api/v1"
}
```

`import.sh` holds one line, `terraform import inventory_host.example <id>`. Run
`go generate ./...` to produce `docs/` and commit the result.
