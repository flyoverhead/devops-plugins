# Building resources and clients

Continues the `inventory` sample from `PROVIDER.md`.

## Contents

- API client
- Resource
- Model conversion
- Data source
- Schema decisions
- Validators, defaults and timeouts
- Long-running operations
- Migrating from SDKv2

## API client

`internal/client` imports nothing from Terraform, so it can be tested with plain `httptest`
servers. One constructor takes the endpoint, the token and a timeout. The base URL is normalised to
end in a slash. A single `do` helper does all I/O: JSON in and out, the bearer header, `Accept` and
`Content-Type`, and the request context. A 404 becomes the sentinel `ErrNotFound`; any other status
of 300 or more becomes an `APIError` that carries the status code and a size-limited detail; a body that
does not decode is wrapped with the request it belongs to. When the service ships an official Go
SDK, wrap it behind the same package API instead of writing HTTP by hand.

**`internal/client/client.go`**

```go
package client

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

var ErrNotFound = errors.New("resource does not exist")

type APIError struct {
	Code   int
	Detail string
}

func (e *APIError) Error() string {
	return fmt.Sprintf("inventory api: HTTP %d: %s", e.Code, e.Detail)
}

type Client struct {
	root   string
	bearer string
	hc     *http.Client
}

func New(endpoint, token string, timeout time.Duration) *Client {
	return &Client{
		root:   strings.TrimRight(endpoint, "/") + "/",
		bearer: token,
		hc:     &http.Client{Timeout: timeout},
	}
}

func (c *Client) do(ctx context.Context, method, path string, payload, out any) error {
	var rdr io.Reader
	if payload != nil {
		buf, err := json.Marshal(payload)
		if err != nil {
			return fmt.Errorf("marshal request for %s %s: %w", method, path, err)
		}
		rdr = bytes.NewReader(buf)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.root+strings.TrimPrefix(path, "/"), rdr)
	if err != nil {
		return fmt.Errorf("create request for %s %s: %w", method, path, err)
	}
	req.Header = http.Header{
		"Authorization": {"Bearer " + c.bearer},
		"Accept":        {"application/json"},
	}
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.hc.Do(req)
	if err != nil {
		return fmt.Errorf("send %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return ErrNotFound
	}
	if resp.StatusCode >= 300 {
		detail, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return &APIError{Code: resp.StatusCode, Detail: strings.TrimSpace(string(detail))}
	}
	if out == nil || resp.StatusCode == http.StatusNoContent {
		return nil
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return fmt.Errorf("parse response of %s %s: %w", method, path, err)
	}
	return nil
}

type Host struct {
	ID        string            `json:"id"`
	Hostname  string            `json:"hostname"`
	IPAddress string            `json:"ip_address"`
	Tags      map[string]string `json:"tags,omitempty"`
}

type HostInput struct {
	Hostname  string            `json:"hostname"`
	IPAddress string            `json:"ip_address"`
	Tags      map[string]string `json:"tags,omitempty"`
}

func (c *Client) CreateHost(ctx context.Context, payload HostInput) (*Host, error) {
	var host Host
	if err := c.do(ctx, http.MethodPost, "hosts", payload, &host); err != nil {
		return nil, err
	}
	return &host, nil
}

func (c *Client) GetHost(ctx context.Context, id string) (*Host, error) {
	var host Host
	if err := c.do(ctx, http.MethodGet, "hosts/"+url.PathEscape(id), nil, &host); err != nil {
		return nil, err
	}
	return &host, nil
}

func (c *Client) UpdateHost(ctx context.Context, id string, payload HostInput) (*Host, error) {
	var host Host
	if err := c.do(ctx, http.MethodPut, "hosts/"+url.PathEscape(id), payload, &host); err != nil {
		return nil, err
	}
	return &host, nil
}

func (c *Client) DeleteHost(ctx context.Context, id string) error {
	return c.do(ctx, http.MethodDelete, "hosts/"+url.PathEscape(id), nil, nil)
}
```

## Resource

A resource implements `resource.Resource`, `ResourceWithConfigure` and `ResourceWithImportState`.

- `Metadata` appends `_host` to the provider type name from the request.
- Attributes: a computed `id` with `UseStateForUnknown`; a required `hostname` with `RequiresReplace`;
  a required `ip_address`; an optional `tags` map of strings.
- `Configure` type-asserts `ProviderData` to the client and adds a diagnostic when the type is
  wrong. Provider data is nil during early validation; return quietly then.
- `Create` and `Update` write state from the API response, not from the plan.
- `Read` removes the resource from state when the API reports not found.
- `Delete` ignores not found.
- Import passes the `id` straight through; a nested resource with a composite id splits it in
  `ImportState` and sets each attribute.

**`internal/provider/host_resource.go`**

```go
package provider

import (
	"context"
	"errors"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework/path"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	rschema "github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/planmodifier"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringplanmodifier"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"github.com/example/terraform-provider-inventory/internal/client"
)

var (
	_ resource.Resource                = (*hostResource)(nil)
	_ resource.ResourceWithConfigure   = (*hostResource)(nil)
	_ resource.ResourceWithImportState = (*hostResource)(nil)
)

type hostResource struct {
	api *client.Client
}

func NewHostResource() resource.Resource {
	return &hostResource{}
}

func (r *hostResource) Metadata(_ context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_host"
}

func (r *hostResource) Schema(_ context.Context, _ resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = rschema.Schema{
		Description: "A host registered in the inventory.",
		Attributes: map[string]rschema.Attribute{
			"id": rschema.StringAttribute{
				Computed:      true,
				Description:   "Identifier assigned by the service.",
				PlanModifiers: []planmodifier.String{stringplanmodifier.UseStateForUnknown()},
			},
			"hostname": rschema.StringAttribute{
				Required:      true,
				Description:   "Host name; a new value creates a new host.",
				PlanModifiers: []planmodifier.String{stringplanmodifier.RequiresReplace()},
			},
			"ip_address": rschema.StringAttribute{
				Required:    true,
				Description: "Primary IP address.",
			},
			"tags": rschema.MapAttribute{
				Optional:    true,
				ElementType: types.StringType,
				Description: "Free-form tags.",
			},
		},
	}
}

func (r *hostResource) Configure(_ context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}
	api, ok := req.ProviderData.(*client.Client)
	if !ok {
		resp.Diagnostics.AddError("Unexpected provider data",
			fmt.Sprintf("Expected *client.Client, got %T.", req.ProviderData))
		return
	}
	r.api = api
}

func (r *hostResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	var want hostModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &want)...)
	if resp.Diagnostics.HasError() {
		return
	}

	payload, d := hostToAPI(ctx, want)
	resp.Diagnostics.Append(d...)
	if resp.Diagnostics.HasError() {
		return
	}

	host, err := r.api.CreateHost(ctx, payload)
	if err != nil {
		resp.Diagnostics.AddError("Creating host failed", err.Error())
		return
	}

	got, d := hostFromAPI(ctx, host, want.Tags)
	resp.Diagnostics.Append(d...)
	resp.Diagnostics.Append(resp.State.Set(ctx, got)...)
}

func (r *hostResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {
	var before hostModel
	resp.Diagnostics.Append(req.State.Get(ctx, &before)...)
	if resp.Diagnostics.HasError() {
		return
	}

	host, err := r.api.GetHost(ctx, before.ID.ValueString())
	if errors.Is(err, client.ErrNotFound) {
		resp.State.RemoveResource(ctx)
		return
	}
	if err != nil {
		resp.Diagnostics.AddError("Reading host failed", err.Error())
		return
	}

	got, d := hostFromAPI(ctx, host, before.Tags)
	resp.Diagnostics.Append(d...)
	resp.Diagnostics.Append(resp.State.Set(ctx, got)...)
}

func (r *hostResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	var want, before hostModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &want)...)
	resp.Diagnostics.Append(req.State.Get(ctx, &before)...)
	if resp.Diagnostics.HasError() {
		return
	}

	payload, d := hostToAPI(ctx, want)
	resp.Diagnostics.Append(d...)
	if resp.Diagnostics.HasError() {
		return
	}

	host, err := r.api.UpdateHost(ctx, before.ID.ValueString(), payload)
	if err != nil {
		resp.Diagnostics.AddError("Updating host failed", err.Error())
		return
	}

	got, d := hostFromAPI(ctx, host, want.Tags)
	resp.Diagnostics.Append(d...)
	resp.Diagnostics.Append(resp.State.Set(ctx, got)...)
}

func (r *hostResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {
	var before hostModel
	resp.Diagnostics.Append(req.State.Get(ctx, &before)...)
	if resp.Diagnostics.HasError() {
		return
	}

	err := r.api.DeleteHost(ctx, before.ID.ValueString())
	if err != nil && !errors.Is(err, client.ErrNotFound) {
		resp.Diagnostics.AddError("Deleting host failed", err.Error())
	}
}

func (r *hostResource) ImportState(ctx context.Context, req resource.ImportStateRequest, resp *resource.ImportStateResponse) {
	resource.ImportStatePassthroughID(ctx, path.Root("id"), req, resp)
}
```

## Model conversion

Each type has one conversion pair in `<noun>_model.go`: `toAPI` from plan to request, `fromAPI`
from response to state. Optional collections follow one rule: when the configuration had null and
the API returns empty, keep null, otherwise Terraform reports a perpetual difference between
`null` and `{}`.

**`internal/provider/host_model.go`**

```go
package provider

import (
	"context"

	"github.com/hashicorp/terraform-plugin-framework/diag"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"github.com/example/terraform-provider-inventory/internal/client"
)

type hostModel struct {
	ID        types.String `tfsdk:"id"`
	Hostname  types.String `tfsdk:"hostname"`
	IPAddress types.String `tfsdk:"ip_address"`
	Tags      types.Map    `tfsdk:"tags"`
}

func hostToAPI(ctx context.Context, m hostModel) (client.HostInput, diag.Diagnostics) {
	payload := client.HostInput{
		Hostname:  m.Hostname.ValueString(),
		IPAddress: m.IPAddress.ValueString(),
	}
	var d diag.Diagnostics
	if !m.Tags.IsNull() && !m.Tags.IsUnknown() {
		d.Append(m.Tags.ElementsAs(ctx, &payload.Tags, false)...)
	}
	return payload, d
}

func hostFromAPI(ctx context.Context, host *client.Host, before types.Map) (hostModel, diag.Diagnostics) {
	m := hostModel{
		ID:        types.StringValue(host.ID),
		Hostname:  types.StringValue(host.Hostname),
		IPAddress: types.StringValue(host.IPAddress),
	}
	if len(host.Tags) == 0 && before.IsNull() {
		m.Tags = types.MapNull(types.StringType)
		return m, nil
	}
	tags := host.Tags
	if tags == nil {
		tags = map[string]string{}
	}
	var d diag.Diagnostics
	m.Tags, d = types.MapValueFrom(ctx, types.StringType, tags)
	return m, d
}
```

## Data source

A data source reads by id, shares `Configure` with the resource pattern, and reuses the same model
conversion. Its attributes are `Required` for the lookup key and `Computed` for everything else.

**`internal/provider/host_data_source.go`**

```go
package provider

import (
	"context"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	dschema "github.com/hashicorp/terraform-plugin-framework/datasource/schema"
	"github.com/hashicorp/terraform-plugin-framework/types"

	"github.com/example/terraform-provider-inventory/internal/client"
)

var (
	_ datasource.DataSource              = (*hostDataSource)(nil)
	_ datasource.DataSourceWithConfigure = (*hostDataSource)(nil)
)

type hostDataSource struct {
	api *client.Client
}

func NewHostDataSource() datasource.DataSource {
	return &hostDataSource{}
}

func (ds *hostDataSource) Metadata(_ context.Context, req datasource.MetadataRequest, resp *datasource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_host"
}

func (ds *hostDataSource) Schema(_ context.Context, _ datasource.SchemaRequest, resp *datasource.SchemaResponse) {
	resp.Schema = dschema.Schema{
		Description: "Reads a host by id.",
		Attributes: map[string]dschema.Attribute{
			"id":         dschema.StringAttribute{Required: true, Description: "Host identifier."},
			"hostname":   dschema.StringAttribute{Computed: true, Description: "Host name as registered."},
			"ip_address": dschema.StringAttribute{Computed: true, Description: "Primary IP address."},
			"tags": dschema.MapAttribute{
				Computed:    true,
				ElementType: types.StringType,
				Description: "Free-form tags.",
			},
		},
	}
}

func (ds *hostDataSource) Configure(_ context.Context, req datasource.ConfigureRequest, resp *datasource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}
	api, ok := req.ProviderData.(*client.Client)
	if !ok {
		resp.Diagnostics.AddError("Unexpected provider data",
			fmt.Sprintf("Expected *client.Client, got %T.", req.ProviderData))
		return
	}
	ds.api = api
}

func (ds *hostDataSource) Read(ctx context.Context, req datasource.ReadRequest, resp *datasource.ReadResponse) {
	var cfg hostModel
	resp.Diagnostics.Append(req.Config.Get(ctx, &cfg)...)
	if resp.Diagnostics.HasError() {
		return
	}

	host, err := ds.api.GetHost(ctx, cfg.ID.ValueString())
	if err != nil {
		resp.Diagnostics.AddError("Reading host failed", err.Error())
		return
	}

	got, d := hostFromAPI(ctx, host, types.MapNull(types.StringType))
	resp.Diagnostics.Append(d...)
	resp.Diagnostics.Append(resp.State.Set(ctx, got)...)
}
```

## Schema decisions

Prefer nested attributes over blocks in new providers.

| Attribute kind | Schema flags | Plan modifier |
|---|---|---|
| Identifier assigned by the API | `Computed` | `UseStateForUnknown` |
| Input that cannot change in place | `Required` or `Optional` | `RequiresReplace` |
| Optional input with an API-side default | `Optional` and `Computed` | `UseStateForUnknown` when stable |
| Secret the user supplies | `Sensitive`; never `Computed` from an echo | none |
| Secret that must not reach state (Terraform 1.11 or later) | `WriteOnly` | none |
| Named collection | map-nested attribute rather than list-nested | none |
| Stable computed value (created-at) | `Computed` | `UseStateForUnknown` |

## Validators, defaults and timeouts

- Enumerations and cross-attribute rules use `terraform-plugin-framework-validators`
  (`stringvalidator.OneOf`, `ConflictsWith`, `AtLeastOneOf`).
- A `Default` needs `Computed: true` on the same attribute.
- Timeouts use `terraform-plugin-framework-timeouts`: add the `timeouts` attribute to the schema,
  a `timeouts.Value` field to the model, and derive the deadline at the top of the operation with
  `plan.Timeouts.Create(ctx, defaultTimeout)` and `context.WithTimeout`.

## Long-running operations

Poll until the object reaches a terminal status. Honour context cancellation between polls, back
off exponentially with a cap of 30 seconds, and put the last observed status in the error when the
deadline passes. Retry only idempotent methods, and only on 429 and 5xx; never retry a POST.

## Migrating from SDKv2

A fork of an upstream SDKv2 provider stays on its SDK and is not migrated. For a provider you own:

1. Serve both implementations through a mux: upgrade the SDKv2 server with `tf5to6server`, then
   combine with `tf6muxserver`.
2. Port one resource at a time, keeping the type name and every attribute name and type.
3. Use `ResourceWithUpgradeState` only when a schema version changes.
4. Test each ported resource with `ExternalProviders` pinned to the last SDKv2 release, followed by
   a step with the new provider and `PlanOnly: true` that expects an empty plan.
5. When the last resource is ported, remove the mux and the SDK dependency.
