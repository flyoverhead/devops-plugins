# Provider validation

## Contents

- The loop
- Client unit tests
- Provider test factories
- Acceptance tests
- CI matrix
- Local try-out
- Review checklist
- Common failures

## The loop

Run from the repository root, repeating each command until it is clean.

```bash
gofmt -l .
go build ./...
go vet ./...
golangci-lint run ./...
go test ./...
go tool tfplugindocs validate
actionlint .github/workflows/*.yml
```

`gofmt -l .` must print nothing. Regenerate documentation with `go generate ./...`, which formats
`examples/` and runs tfplugindocs. Acceptance tests run with `TF_ACC=1 go test ./...` against the
in-process fake API described below. A real API is used only when the user asks for it and
supplies the endpoint and token in their own environment. Commands that need the network may fail
in a sandbox; report the error instead of working around it.

## Client unit tests

Table-driven tests with `t.Run`, one `httptest` server per case. Check the `Authorization`
header, one success path, and the not-found path with `errors.Is(err, client.ErrNotFound)`.

**`internal/client/client_test.go`**

```go
package client

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func stubServer(t *testing.T, status int, body string) *Client {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer secret" {
			t.Errorf("unexpected Authorization header %q", r.Header.Get("Authorization"))
		}
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	}))
	t.Cleanup(srv.Close)
	return New(srv.URL, "secret", 5*time.Second)
}

func TestGetHostOutcomes(t *testing.T) {
	cases := map[string]struct {
		status int
		body   string
		check  func(t *testing.T, h *Host, err error)
	}{
		"found": {
			status: http.StatusOK,
			body:   `{"id":"h-1","hostname":"a","ip_address":"10.0.0.1"}`,
			check: func(t *testing.T, h *Host, err error) {
				if err != nil || h.ID != "h-1" || h.IPAddress != "10.0.0.1" {
					t.Fatalf("got %+v, %v", h, err)
				}
			},
		},
		"missing": {
			status: http.StatusNotFound,
			check: func(t *testing.T, _ *Host, err error) {
				if !errors.Is(err, ErrNotFound) {
					t.Fatalf("err = %v, want ErrNotFound", err)
				}
			},
		},
		"server error": {
			status: http.StatusInternalServerError,
			body:   "boom",
			check: func(t *testing.T, _ *Host, err error) {
				var apiErr *APIError
				if !errors.As(err, &apiErr) || apiErr.Code != http.StatusInternalServerError {
					t.Fatalf("err = %v, want APIError with status 500", err)
				}
			},
		},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			h, err := stubServer(t, tc.status, tc.body).GetHost(context.Background(), "h-1")
			tc.check(t, h, err)
		})
	}
}
```

## Provider test factories

The factory map starts the provider in process over protocol 6. A pre-check helper picks the
backend: with both `INVENTORY_ENDPOINT` and `INVENTORY_TOKEN` set it uses the real service;
otherwise it starts an in-memory fake HTTP handler that implements create, read, update and delete
on the collection with `ServeMux` method patterns, and points the provider at it with `t.Setenv`.
Because of `t.Setenv`, these tests do not use `t.Parallel`.

**`internal/provider/provider_test.go`**

```go
package provider

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"sync"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/providerserver"
	"github.com/hashicorp/terraform-plugin-go/tfprotov6"

	"github.com/example/terraform-provider-inventory/internal/client"
)

var protoFactories = map[string]func() (tfprotov6.ProviderServer, error){
	"inventory": providerserver.NewProtocol6WithError(New("test")()),
}

func useBackend(t *testing.T) {
	t.Helper()
	if os.Getenv("INVENTORY_ENDPOINT") != "" && os.Getenv("INVENTORY_TOKEN") != "" {
		return
	}
	srv := httptest.NewServer(newFakeAPI())
	t.Cleanup(srv.Close)
	t.Setenv("INVENTORY_ENDPOINT", srv.URL+"/api/v1")
	t.Setenv("INVENTORY_TOKEN", "test-token")
}

type fakeAPI struct {
	mu    sync.Mutex
	seq   int
	hosts map[string]client.Host
}

func newFakeAPI() http.Handler {
	f := &fakeAPI{hosts: map[string]client.Host{}}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/hosts", f.create)
	mux.HandleFunc("GET /api/v1/hosts/{id}", f.get)
	mux.HandleFunc("PUT /api/v1/hosts/{id}", f.update)
	mux.HandleFunc("DELETE /api/v1/hosts/{id}", f.remove)
	return mux
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func (f *fakeAPI) create(w http.ResponseWriter, r *http.Request) {
	var payload client.HostInput
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	f.seq++
	host := client.Host{ID: fmt.Sprintf("host-%d", f.seq), Hostname: payload.Hostname, IPAddress: payload.IPAddress, Tags: payload.Tags}
	f.hosts[host.ID] = host
	writeJSON(w, http.StatusCreated, host)
}

func (f *fakeAPI) get(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	host, ok := f.hosts[r.PathValue("id")]
	if !ok {
		http.NotFound(w, r)
		return
	}
	writeJSON(w, http.StatusOK, host)
}

func (f *fakeAPI) update(w http.ResponseWriter, r *http.Request) {
	var payload client.HostInput
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	id := r.PathValue("id")
	if _, ok := f.hosts[id]; !ok {
		http.NotFound(w, r)
		return
	}
	host := client.Host{ID: id, Hostname: payload.Hostname, IPAddress: payload.IPAddress, Tags: payload.Tags}
	f.hosts[id] = host
	writeJSON(w, http.StatusOK, host)
}

func (f *fakeAPI) remove(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	id := r.PathValue("id")
	if _, ok := f.hosts[id]; !ok {
		http.NotFound(w, r)
		return
	}
	delete(f.hosts, id)
	w.WriteHeader(http.StatusNoContent)
}
```

## Acceptance tests

One test per resource, with three steps: create and check, import with verification, in-place
update and check.

- Names come from `acctest.RandomWithPrefix("tfacc")`.
- `CheckDestroy` reads each remaining object through the client and expects `client.ErrNotFound`.
- A data source is tested by creating the resource and reading it back in the same configuration.
- `resource.Test` skips unless `TF_ACC` is set. It finds the Terraform binary on `PATH`, or from
  `TF_ACC_TERRAFORM_PATH`.
- Fields the API never returns go into `ImportStateVerifyIgnore`.

**`internal/provider/host_resource_test.go`**

```go
package provider

import (
	"context"
	"errors"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/hashicorp/terraform-plugin-testing/helper/acctest"
	"github.com/hashicorp/terraform-plugin-testing/helper/resource"
	"github.com/hashicorp/terraform-plugin-testing/terraform"

	"github.com/example/terraform-provider-inventory/internal/client"
)

func testAccHostConfig(name, address string) string {
	return fmt.Sprintf(`
resource "inventory_host" "test" {
  hostname   = %q
  ip_address = %q
  tags       = { env = "test" }
}

data "inventory_host" "test" {
  id = inventory_host.test.id
}
`, name, address)
}

func testAccCheckHostDestroy(s *terraform.State) error {
	c := client.New(os.Getenv("INVENTORY_ENDPOINT"), os.Getenv("INVENTORY_TOKEN"), 30*time.Second)
	for _, rs := range s.RootModule().Resources {
		if rs.Type != "inventory_host" {
			continue
		}
		_, err := c.GetHost(context.Background(), rs.Primary.ID)
		if err == nil {
			return fmt.Errorf("host %s still exists", rs.Primary.ID)
		}
		if !errors.Is(err, client.ErrNotFound) {
			return err
		}
	}
	return nil
}

func TestAccHostResource(t *testing.T) {
	name := acctest.RandomWithPrefix("tfacc")

	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { useBackend(t) },
		ProtoV6ProviderFactories: protoFactories,
		CheckDestroy:             testAccCheckHostDestroy,
		Steps: []resource.TestStep{
			{
				Config: testAccHostConfig(name, "10.0.0.5"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("inventory_host.test", "hostname", name),
					resource.TestCheckResourceAttrSet("inventory_host.test", "id"),
					resource.TestCheckResourceAttrPair("data.inventory_host.test", "ip_address", "inventory_host.test", "ip_address"),
				),
			},
			{
				ResourceName:      "inventory_host.test",
				ImportState:       true,
				ImportStateVerify: true,
			},
			{
				Config: testAccHostConfig(name, "10.0.0.6"),
				Check:  resource.TestCheckResourceAttr("inventory_host.test", "ip_address", "10.0.0.6"),
			},
		},
	})
}
```

## CI matrix

The acceptance matrix in `test.yml` covers the two latest Terraform minor releases, written as
`<major>.<minor>.*`. Look the current latest release up on the Terraform releases page
(`releases.hashicorp.com/terraform`) when the workflow is written and again on every provider
change; do not copy numbers from an older workflow.

## Local try-out

Install the provider and point a CLI configuration at it:

```bash
go install .
cat > /tmp/inventory.tfrc <<EOF
provider_installation {
  dev_overrides {
    "registry.terraform.io/example/inventory" = "$(go env GOPATH)/bin"
  }
  direct {}
}
EOF
export TF_CLI_CONFIG_FILE=/tmp/inventory.tfrc
```

With `dev_overrides`, skip `terraform init`. Running `terraform plan` against a real API is the
user's step.

## Review checklist

- [ ] `Read` removes the resource on not found; `Delete` tolerates not found
- [ ] every resource has `ImportState` and an import step in its test
- [ ] non-updatable attributes have `RequiresReplace`; stable computed ones `UseStateForUnknown`
- [ ] unset optional attributes stay null after read
- [ ] credentials are `Sensitive`, optional with an environment fallback, and never logged
- [ ] unknown values are checked before they reach the client
- [ ] diagnostics instead of panics
- [ ] acceptance tests pass against the fake API without credentials
- [ ] `docs/` regenerated and committed; `.goreleaser.yml` passes `goreleaser check`

## Common failures

| Symptom | Fix |
|---|---|
| `Provider produced inconsistent result after apply` | State was built from the plan. Build it from the API response, and set every computed value |
| Perpetual diff between `{}` or `""` and null | Keep null when the configuration had null and the API returned empty; see the model conversion rule |
| `Value Conversion Error` | The model field type differs from the schema (`types.String` versus `types.Map`, missing `tfsdk` tag). Align them |
| An unknown value reaches the client | Check `IsUnknown()` in `Configure` and before conversion |
| Import verify fails on a secret | The API does not return it. Add it to `ImportStateVerifyIgnore` |
| golangci-lint config error mentioning v1 keys | The file is v2 format. Use `version: "2"`, `linters.default` and `formatters` instead of the v1 keys |
