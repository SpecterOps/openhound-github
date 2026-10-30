<p align="center">
  <a href="https://specterops.io" target="_blank">
    <img alt="A project powered by SpecterOps - Creators of BloodHound" src="https://raw.githubusercontent.com/SpecterOps/OpenHound/refs/heads/main/.github/GitHub-Header.png" width="100%" style="max-width: 100%;">
  </a>
</p>

<h4 align="center">
  Github collector for OpenHound
</h4>

<!-- Standard shields, please do not remove -->
<p align="center">
  <a href="https://slack.specterops.io"><img src="https://custom-icon-badges.demolab.com/badge/Slack-BloodHound%20Gang-4A154B?logo=slack&logoColor=fff" alt="Slack"/></a>
  <a href="https://reddit.com/r/SpecterOpsCommunity"><img src="https://img.shields.io/badge/Reddit-r/SpecterOpsCommunity-FF4500?logo=reddit&logoColor=white" alt="SpecterOps on Reddit"/></a>
  <a href="https://github.com/specterops"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fspecterops%2F.github%2Fmain%2Fconfig%2Fshield.json&style=flat" alt="Sponsored by SpecterOps"/></a>
</p>


<p align="center">
  <a href="https://x.com/SpecterOps"><img src="https://img.shields.io/twitter/follow/SpecterOps?style=social" alt="@SpecterOps on Twitter"/></a>
  <a href="https://www.linkedin.com/company/specterops/"><img src="https://custom-icon-badges.demolab.com/badge/LinkedIn-0A66C2?logo=linkedin-white&logoColor=fff" alt="Connect on LinkedIn"/></a>
  <a href="https://infosec.exchange/@specterops"><img src="https://img.shields.io/mastodon/follow/109314317500800201?domain=https%3A%2F%2Finfosec.exchange&style=social" alt="Connect on Mastodon"/></a>
</p>

---

## About

OpenHound is a standardized framework for building and running OpenGraph collectors and converters. It is built in
Python and powered by the [Data Load Tool (DLT)](https://dlthub.com/docs/intro) library, giving you a consistent
workflow to collect, process, and convert data from any source into BloodHound-compatible graphs.

The openhound-github extension collects resources from Github organizations and transforms these into useable nodes and
edges for
BloodHound.

### GitHub App JWT issuer

Enterprise GitHub App credentials accept either `client_id` or `app_id` as the
JWT issuer. When both are configured, `client_id` is preferred. At least one
identifier must be supplied together with `key_path` and `enterprise_name`.

### GitHub Enterprise Server endpoints

GitHub.com is the default deployment and does not require endpoint configuration.
To collect from GitHub Enterprise Server, set both API endpoints in `config.toml`:

```toml
[sources.github]
rest_api_url = "https://ghe.example/api/v3"
graphql_url = "https://ghe.example/api/graphql"
```

Both values must be provided together when overriding the GitHub.com defaults.
Endpoint URLs must use HTTPS and share the same origin. GitHub App
`credentials.api_uri` may override only the path on that same origin.

### Request timeouts and retries

REST and GraphQL collection requests use a 10-second connection timeout and a
30-second read timeout. Transient HTTP 5xx errors, connection failures, and
timeouts share a limit of three attempts (the initial attempt plus two retries).
Adaptive GraphQL pagination shares that limit across page sizes: HTTP 502/504
responses trigger smaller-page attempts instead of a new retry budget.

After retries are exhausted, existing resource handlers log the failure and
continue with unaffected scopes. Already emitted records are retained, but the
affected scope may be incomplete. Resources that require all pages before
emitting records retain that behavior.

Rate-limit responses and GitHub App token refresh retain their existing retry
handling and do not consume the transient-failure budget. These timeouts are
not an overall request deadline. App authentication requests and credential
inventory CSV downloads retain their separate timeout settings.

### Enterprise SCIM and hybrid correlations

A token with enterprise SCIM access is used to collect both `/scim/v2/enterprises/{enterprise}/Users` and `/scim/v2/enterprises/{enterprise}/Groups`. The collector emits normalized `SCIM_Organization`, `SCIM_User`, and `SCIM_Group` nodes plus `SCIM_Contains`, `SCIM_MemberOf`, and `SCIM_Provisioned` relationships. Install the BloodHound SCIM extension alongside this extension to register the shared SCIM kinds.

`SOURCES__GITHUB__EMIT_LEGACY_SCIM_CORRELATIONS=true` temporarily reproduces GitHound-style Okta-to-SCIM correlation relationships. It defaults to false because a dedicated hybrid correlator should own IdP-to-SCIM matching; GitHub remains authoritative for GitHub's SCIM resources and target-system provisioning relationships.

Enterprise roles, including the built-in `members` role, are emitted through `GH_HasRole` and granular enterprise capability relationships. Only capability relationships with a confirmed privilege path are traversable; descriptive permissions such as `GH_WriteEnterpriseSso` remain non-traversable.

### Optional privileged collection

The collector runs successfully with the documented read-only permission set. Some higher-fidelity relationships require optional non-read-only permissions because GitHub exposes the supporting read APIs behind privileged permission names:

- Organization `Members: write` enables external group mapping collection for IdP-synced teams, which allows the converter to emit `SCIM_Provisioned` edges from `SCIM_Group` to `GH_Team`. This is useful when the organization uses team synchronization with an external identity provider; if no GitHub teams are linked to external groups, this permission does not add graph data.
- Classic PAT scope `manage_runners:enterprise` enables enterprise self-hosted runner group and runner collection. This is useful when the enterprise has enterprise-scoped runner groups or runners, especially runner groups shared into organizations; if all runners are organization- or repository-scoped, this scope does not add graph data.
- Repository `Administration: read` enables deploy key collection. GitHub exposes repository deploy keys through an administration-scoped read endpoint, and the collector emits `GH_DeployKey` nodes only when that endpoint is accessible.

If these optional permissions are not granted, OpenHound skips the affected resources and continues collecting the rest of the GitHub environment.

### Selected GitHub App installation repositories

For organization installations limited to selected repositories, the collector
uses the enterprise installation's read-only organization-installation
repositories API to create exact `GH_CanAccess` edges. Grant the enterprise
installation **Enterprise organization installations: read** or **Enterprise
organization installation repositories: read**. Without either permission,
selected-repository edges are skipped; installations set to `all` continue to
use the collected organization repository inventory.

Installation discovery still uses each organization's API and requires
**Organization administration: read** on that organization's credential. The
enterprise permission alone does not discover installations.
The selected-repository lookup runs one installation at a time and stops for
the rest of a collection if GitHub rate-limits it after retries.

### Classic personal access token inventory

With GitHub Enterprise Cloud credentials, the collector uses the enterprise
credential inventory export to collect classic personal access tokens. It
requests the full inventory, stores every CSV row and its original field values
in the `enterprise_credential_inventory` resource, and currently models only
classic PAT rows. The export contains credential metadata, including owners,
scopes, authorization details, and token hashes used for audit correlation. It
does not contain plaintext PAT values. Limit access to the raw output to people
who need the credential inventory.

The enterprise GitHub App needs **Enterprise credentials: read** permission.
When collecting with a classic PAT instead of an app installation, that token
needs the `read:enterprise` scope. If an enterprise app also has
`credentials.pat_token` configured, the app remains the primary export
credential. The collector retries once with the PAT only when GitHub rejects
the app's export creation for authorization. It does not switch credentials
after an export starts or when GitHub reports a rate limit.

Rate-limit retry warnings identify the affected method and API path.

The CSV download is streamed, but the parsed export is held in memory as one
raw record; very large enterprises may need a chunked raw-resource design.

GitHub limits the number of exports an enterprise can start per day. When the
last successful export was downloaded within the past 24 hours, the collector
downloads it again before trying to start a new export. If GitHub reports that
the saved export is gone, the collector starts a new one and polls until its
CSV is ready. GitHub may still reject a new export when its limit is reached.
The raw record's `as_of` value and each PAT node's `inventory_as_of` value
show when that snapshot was taken. An unavailable or denied export is logged
and does not stop other resources from collecting.

Classic PAT nodes include the owner, scopes, lifecycle dates, credential
state, direct enterprise authorization, and total authorization count.
Organization edges record authorizations reported in the export. The
export does not enumerate repositories accessible to a classic PAT, so this
collection does not emit classic PAT-to-repository access edges. Potential
repository access can be derived from the token owner's repository roles and
the token's scopes, subject to organization policy and SSO authorization; it
is not a direct grant reported by the export. GitHub Enterprise Server and
organization-only configurations skip this resource.

[![Python Version](https://img.shields.io/badge/Python-3.13-brightgreen.svg)](#about)

## Getting Started

Follow the OpenHound GitHub collector docs to get started:

- [GitHub collector overview](https://bloodhound.specterops.io/openhound/collectors/github/overview)
- [Configure the collector](https://bloodhound.specterops.io/openhound/collectors/github/collect-data)
- [Configure an organization GitHub App](https://bloodhound.specterops.io/openhound/collectors/github/configure-app)
- [Configure an enterprise GitHub App](https://bloodhound.specterops.io/openhound/collectors/github/configure-enterprise-app)
- [Configure a personal access token](https://bloodhound.specterops.io/openhound/collectors/github/configure-pat)

## Container images

After a release-triggering pull request merges into `main` in
`SpecterOps/openhound-github`, the release workflow publishes the PyPI package
first, then builds images for `linux/amd64` and `linux/arm64` in GitHub Container
Registry. Container builds are skipped for forks, other branches, and standalone
tag pushes. Both images use the same release version:

- `ghcr.io/specterops/openhound-github:<version>` starts the BloodHound Enterprise scheduler.
- `ghcr.io/specterops/openhound-github:<version>-cli` runs the OpenHound CLI.

For example, release tag `v0.20.0` produces image tags `0.20.0` and `0.20.0-cli`.
Use a version containing the container files; releases predating this workflow
cannot be built without backporting those files.

Each release also updates `latest` for the scheduler and `latest-cli` for the
CLI. These aliases point to the same images as that release's versioned tags.
Use versioned tags to pin a deployment. To update a Compose deployment using
`latest`, run `docker compose pull` followed by `docker compose up -d`.

### Run the scheduler

For a complete Compose setup with configuration templates, persistent storage,
and a preflight check, see [docker-compose/README.md](docker-compose/README.md).

Prepare your `.dlt/config.toml`, `.dlt/secrets.toml`, and GitHub App private key
following the collector configuration documentation above. Mount the directory
read-only and use the container path for the key (for example,
`/app/.dlt/github-app.pem`). The container runs as UID/GID `65532`; mounted
files must be readable by that user.

```sh
docker run --rm --init \
  --mount type=bind,src="$(pwd)/.dlt",dst=/app/.dlt,readonly \
  ghcr.io/specterops/openhound-github:<version>
```

Set the BloodHound Enterprise destination URL, token ID, and token key in
`.dlt/secrets.toml`:

```toml
[destination.bloodhoundenterprise]
url = "https://<tenant>.bloodhoundenterprise.io"
token_id = "<token-id>"
token_key = "<token-key>"
```

The image defaults the collector name to `github`. OpenHound manages the
scheduler polling interval internally. Collection state and output are stored
inside the container unless you mount persistent storage for them.

To inspect the CLI:

```sh
docker run --rm ghcr.io/specterops/openhound-github:<version>-cli --help
```

### Build and publish

To build locally without publishing:

```sh
docker build --target cli --build-arg COLLECTOR_VERSION=0.20.0 \
  -t openhound-github:0.20.0-cli .
docker build --target enterprise --build-arg COLLECTOR_VERSION=0.20.0 \
  -t openhound-github:0.20.0 .
```

`COLLECTOR_VERSION` sets the GitHub collector package version; the OpenHound
framework version is resolved separately from `uv.lock`. The container-only
dependency group installs the framework without development tools.

To retry a failed container publication, re-run the failed jobs in the original
release workflow run. The container workflow authenticates using `GITHUB_TOKEN`
with `packages: write`; AWS credentials and personal access tokens are not
needed. Runtime checks run before each image is pushed, and both architectures
include an SBOM.

After the first publication, a package administrator should verify the GHCR
package's visibility and repository access. New packages default to private;
make the package public if anonymous pulls are intended. If the package
already exists, grant this repository's Actions workflows write access to it.
