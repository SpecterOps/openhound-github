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

### Version 0.23.0

This release adds enterprise OIDC providers and external identities, collects the
authenticating GitHub App's enterprise installation metadata, and corrects Tier
Zero role matching and expired-token filtering.

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

### GraphQL repository batch size

Repository metadata is queried in batches of 50 repositories by default. Override
this in `.dlt/config.toml`:

```toml
[sources.github]
graphql_repository_batch_size = 50
```

Or set `SOURCES__GITHUB__GRAPHQL_REPOSITORY_BATCH_SIZE`. The setting accepts integers
from 1 to 100 and controls repositories per request. Gateway failures split batches larger than 25.
At 25 or fewer repositories, two retries wait 1–2 seconds and 15 seconds before
further splitting isolates failures. Unresolved repositories are logged and
collection continues with the remaining batches.

### Initial branches per repository

The initial GraphQL query fetches up to 50 branches per repository by default.
Set `graphql_initial_branch_count` in `.dlt/config.toml`, or use
`SOURCES__GITHUB__GRAPHQL_INITIAL_BRANCH_COUNT`, to choose a value from 1 to 100:

```toml
[sources.github]
graphql_repository_batch_size = 50
graphql_initial_branch_count = 10
```

This setting changes the initial query size, not the total branches collected.
Remaining branches are fetched in pages of 100. GitHub-reported branch totals
and branch protection rule discovery are preserved.

Start with 50. Try 25 or 10 if initial repository queries repeatedly time out or
need splitting, particularly when many repositories have numerous branches.
Smaller initial limits reduce query payloads but add overflow requests; branch
collection and protection-rule discovery currently fetch overflow separately.
A larger limit can help when overflow requests dominate and initial queries
already succeed reliably. Compare elapsed time, gateway failures, and per-repository
completeness on the same inventory, changing one setting at a time. Total branch
count alone does not determine the best value.

### Repository batch diagnostics

At INFO level, repository GraphQL collection logs a summary for each organization:
requested, emitted, and unresolved repository counts; initial batches that succeeded
on the first attempt, recovered, or remained incomplete; batch attempts, failed
attempts, splits, and cumulative request time. A batch with any unresolved repository
is counted as incomplete even if some of its repositories recovered.

For request membership and timings, temporarily enable DEBUG logging in
`.dlt/config.toml`:

```toml
[runtime]
log_level = "DEBUG"
log_cli_level = "DEBUG"
```

DEBUG records include organization, original batch number, attempt number,
repository IDs/names, configured initial branch count, HTTP status, request duration,
and returned/unresolved counts. The new diagnostics omit credentials, query text,
and response bodies. DEBUG also enables verbose output from other components.

Batch attempts count calls to the HTTP client; internal HTTP retries may make
additional network requests. Request duration includes those internal retries and
waits but excludes delays between batch retries, overflow requests, normalization,
and output writing. The organization summary is emitted when its batch iterator
finishes; an interrupted collection may have no summary.

### Request timeouts and retries

REST and GraphQL collection requests use a 10-second connection timeout and a
30-second read timeout. Transient HTTP 5xx errors, connection failures, and
timeouts share a limit of three attempts (the initial attempt plus two retries).
Adaptive GraphQL pagination shares that limit across page sizes: HTTP 502/504
responses trigger smaller-page attempts instead of a new retry budget. Gateway
failures at the smallest page size receive up to two additional attempts with
1–2-second and 15-second delays.

Organization team pagination uses team page sizes of 100, 50, and 25 for this
recovery, retaining the failed cursor until a page succeeds. Already emitted
teams are retained, and member pagination beyond the first 100 members continues
independently. An unrecovered team page logs a collection gap with the
organization, cursor, final page size, and emitted team count before collection
continues with the next organization.

After retries are exhausted, existing resource handlers log the failure and
continue with unaffected scopes. Already emitted records are retained, but the
affected scope may be incomplete. Resources that require all pages before
emitting records retain that behavior.

Workflow collection skips `dynamic/` paths. Missing workflow files are logged
and skipped without passing failed items to job or step parsing.

Rate-limit responses and GitHub App token refresh retain their existing retry
handling and do not consume the transient-failure budget. These timeouts are
not an overall request deadline. App authentication requests and credential
inventory CSV downloads retain their separate timeout settings.

### Branch protection allowance recovery

Branch protection actors are collected through GraphQL. If GitHub returns a
partial error for push or pull-request bypass allowances, the collector retrieves
REST protection details for a representative branch of the affected rule. It
merges users, teams, and apps with successfully collected GraphQL actors,
deduplicating identities and retaining the rest of the rule. Successful GraphQL
responses do not trigger this additional request. Failed or incomplete recovery
logs an explicit allowance collection gap while preserving known actors.

### Branch creation eligibility

Branch creation preprocessing separates shared repository eligibility from
actor-specific bypasses. Restrictions on exact branch names or literal namespaces
such as `release/*`, and substring patterns such as `*protections_test*`, leave
other names available. Broad creation restrictions and
unrecognized patterns exclude shared eligibility; role bypasses are evaluated
separately. A collected default branch is required, and unresolved protection-rule
references exclude shared eligibility. This conservative check uses collected
classic branch protections, does not resolve overlapping-rule precedence, and
does not evaluate rulesets or prove that the protection inventory is complete.

Active organization App installations with granted `contents:write` receive
traversable `GH_CanCreateBranch` paths. All-repository installations use a shared
`GH_Scope` (`scope_type=repository_branch_creation`, `scope=unrestricted`) with
`GH_ScopedTo` membership; selected grants and qualifying App push allowances use
direct repository edges. Empty scopes receive no capability edge. Older
collections without the scope record use direct repository edges instead.
Archived or disabled repositories are excluded. Repository access scopes retain
their existing meaning, and no branch-write or deployment capability is implied.

### App registration management

Organization owners and predefined App manager roles receive traversable
`GH_CanManageApp` edges to Apps registered to their exact owning account.
Enterprise owners and enterprise App managers similarly control enterprise-owned
registrations. Composition queries show the role, its account, and App ownership;
existing user/team assignments and `GH_InstalledAs` carry the resulting paths.
Older collections' `source=Predefined` roles are recognized even with empty
permission arrays and a legacy `type=custom` label. Per-App manager assignments
are not yet enumerated. Re-run preprocessing and conversion, then reimport the
extension schema to display these capabilities and their entity panels.

### Role permission catalog

The preparatory catalog in `src/openhound_github/data/role_permissions.json`
preserves the supplied role definitions, native permission names, target types,
and source checksum. Supplemental target mappings record explicit user
classifications separately from the original definitions. It is a partial snapshot, not a complete definition of
current GitHub permissions. Missing built-in baselines and unresolved role
targets are tracked explicitly; collected API declarations are not automatically
overwritten or supplemented by the snapshot.

Catalog helpers classify native actions into `permissions_repository`,
`permissions_organization`, and `permissions_enterprise` using declared resource
targets (`Business` maps to enterprise). Unknown actions and unsupported targets
are retained in `permissions_unclassified`, without guessing from their names.
Direct built-in lists exclude permissions supplied by their explicit base chain;
cross-resource inheritance remains a role relationship. Roles are identified by
both name and target type, so equal names at different scopes remain distinct.

Repository, organization, and enterprise role nodes export these scoped arrays
and a nullable `base_role`. API permission lists (including empty lists) are
preserved as direct grants. Collector-synthesized built-ins use verified catalog
baselines; missing synthesized baselines export empty placeholder arrays until
their definitions are added. These placeholders do not imply the roles lack
permissions. Enterprise role nodes export scoped
arrays in place of the former unscoped `permissions` property. Raw collected
permission lists are retained for existing evaluators.

Existing role inheritance and capability edges continue to use their current
logic; the new properties do not drive permission evaluation. Organization
roles with explicit repository permissions also receive a non-traversable
`GH_CanAccess` edge to their organization's all-repositories `GH_Scope`.
Roles with only inherited repository permissions keep their `GH_HasBaseRole`
edges without an additional repository scope edge. Organization-only roles do
not receive this edge.
Each repository, organization, and enterprise role also has an unconditional,
non-traversable `GH_CanAccess` edge to its exact parent resource, including roles
whose direct permission arrays are empty or pending baseline definitions.

Repository, organization, and enterprise role nodes do not export `query_*`
properties.
Organization role schema panels
provide direct inbound assignments, Effective Members, Inherited Role Paths,
and organization access through `GH_CanAccess`.

Role graph IDs use `GH_RR_` (repository), `GH_OR_` (organization), and `GH_ER_`
(enterprise), followed by unpadded Base64url-encoded MessagePack:
`[1, parent_database_id, "builtin" | "api", role_key_or_id]`. These are collector
IDs, not native GitHub node IDs. The graph `id` and `node_id` property match.
Collector-synthesized roles use a stable name key; API roles, including predefined
ones, use their numeric role ID so renaming them preserves identity. Parent IDs
come from collected numeric database IDs. `github_role_id` retains the source
record's ID. Assignments, inheritance, capability edges, and composition queries
use the same encoded role identities. Refresh the lookup and graph with
preprocess/convert; no recollection is needed when parent database IDs and role
records are already present.

### Enterprise SCIM and hybrid correlations

A token with enterprise SCIM access is used to collect both `/scim/v2/enterprises/{enterprise}/Users` and `/scim/v2/enterprises/{enterprise}/Groups`. The collector emits normalized `SCIM_Organization`, `SCIM_User`, and `SCIM_Group` nodes plus `SCIM_Contains`, `SCIM_MemberOf`, and `SCIM_Provisioned` relationships. Install the BloodHound SCIM extension alongside this extension to register the shared SCIM kinds.

For both organization and enterprise SCIM collection, `SCIM_Organization.objectid`
is the scope's `scim_base_url`, and SCIM users and groups use that URL as their
`environmentid`. Existing `SCIM_Contains` edges reference this organization ID.
The SCIM organization's own `environmentid` remains its hosting GitHub scope ID.
This replaces the previous `SCIM_Organization_<GitHub scope ID>` identifier;
previously ingested organization nodes are not renamed automatically. SCIM input
records now require `scim_base_url`, so recollect older SCIM data before conversion.

SCIM users expose `groups` as an array of group ID strings from membership `value`
fields. Membership objects remain in collected input, and `SCIM_MemberOf` edges
are preserved. The `roles` graph property remains a JSON-encoded string.

Explicitly active SCIM users receive a direct `SCIM_Provisioned` edge to their
mapped `GH_User` when the SCIM GUID resolves to one external identity in the same
GitHub scope and that identity has an unambiguous GitHub user ID. Missing or
ambiguous mappings emit no provisioning edge. `GH_ExternalIdentity` nodes and
their `GH_MapsToUser` edges remain; SCIM users no longer provision the external
identity node.

`SOURCES__GITHUB__EMIT_LEGACY_SCIM_CORRELATIONS=true` temporarily reproduces GitHound-style Okta-to-SCIM correlation relationships. It defaults to false because a dedicated hybrid correlator should own IdP-to-SCIM matching; GitHub remains authoritative for GitHub's SCIM resources and target-system provisioning relationships.

In enterprise app authentication mode, the collector separately retrieves its own enterprise installation for configuration troubleshooting, including granted permissions, timestamps, and suspension status. It also retrieves the parent app's requested permissions and owner metadata using the enterprise installation token. This does not enumerate other enterprise-target app installations or imply organization/repository access. App and installation records use `environment_slug` for the organization login or enterprise slug. Installations also retain `target_type` to distinguish targets; older collected records remain compatible. Existing DLT app schemas are migrated to allow empty legacy `org_login` fields and absent `repository_selection`. A load already stuck in normalization retains its saved schema and needs recovery or restart; do not delete the pipeline or collected output to apply this change.

Enterprise roles, including the built-in `members` role, are emitted through `GH_HasRole` and granular enterprise capability relationships. Only capability relationships with a confirmed privilege path are traversable; descriptive permissions such as `GH_WriteEnterpriseSso` remain non-traversable.

### Enterprise OIDC collection

A supplemental classic PAT owned by an enterprise owner with `read:enterprise`
enables discovery of `enterprise.ownerInfo.oidcProvider`. The collector stores
provider metadata in `oidc_provider` and emits `GH_OidcIdentityProvider` with
`provider_type` and `tenant_id`, linked to the enterprise through the
non-traversable `GH_HasOidcIdentityProvider` relationship.

SAML and OIDC providers both carry the secondary kind `GH_IdentityProvider`.
Provider queries run independently, so an unavailable OIDC field or denied
request does not prevent existing SAML collection. An absent OIDC provider is
logged separately from query failures.

External identities from both enterprise provider types are paginated into the
existing `external_identities` table. Conversion resolves their provider through
the SAML and OIDC metadata tables and emits `GH_HasExternalIdentity` and, when a
linked user exists, `GH_MapsToUser`. These edges remain non-traversable. Nullable
identity attributes and unlinked identities are retained. OIDC identities do not
produce SAML account relationships. If provider lookup is missing or ambiguous,
conversion omits the provider edge while preserving the identity and user mapping;
ambiguous matches are logged.

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

Publishing a GitHub Release runs tests against its tag, builds and publishes the
PyPI package, then builds images for `linux/amd64` and `linux/arm64` in GitHub
Container Registry. Merging PRs and pushing tags do not publish artifacts.
Both images use the same release version:

- `ghcr.io/specterops/openhound-github:<version>` starts the BloodHound Enterprise scheduler.
- `ghcr.io/specterops/openhound-github:<version>-cli` runs the OpenHound CLI.

For example, release tag `v0.20.0` produces image tags `0.20.0` and `0.20.0-cli`.
Use a version containing the container files; releases predating this workflow
cannot be built without backporting those files.

The newest published stable version updates `latest` for the scheduler and
`latest-cli` for the CLI. Prereleases and older stable versions do not move these
aliases. These aliases point to the same images as the selected release's versioned tags.
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

Maintainers can merge several PRs before releasing. In GitHub, create a draft
release, choose a version tag (for example `v0.25.0`), and target the intended
commit on `main`. Review the included changes, then publish the release to start
the workflow. Draft releases do not publish packages or images. For a prerelease,
use a tag such as `v0.25.0rc1` and mark the GitHub Release as a prerelease; only
versioned image tags are published. Branch name prefixes no longer select or
increment release versions.

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

### Enterprise team identities and repository access

Breaking graph-model change, accompanied by OpenGraph schema `v1.5.0`
(previously `v1.4.3`). Deploy the updated schema, saved searches, and collector
together. Select an appropriate collector release version when publishing;
the collector package version is generated from the release tag.

Enterprise teams use one native `ET_` node ID across all assigned organizations.
Organization REST team observations are retained in `projected_enterprise_teams`
for identity lookup but no longer emit synthetic `GH_Team` nodes. The collector
prefers returned native IDs; otherwise it derives the observed MessagePack ID
from the enterprise and team database IDs. Unrecognized enterprise encodings or
conflicting observations fail rather than inventing a replacement identity.

Repository grants are collected for each assigned organization using
`GET /organizations/{org_id}/team/{team_id}/repos` with that organization's client.
`GH_AssignedTo` links the enterprise team to organizations; `GH_HasRole` links it
directly to repository roles. Organization client access is required for grants.

Recollect, preprocess, and convert to include these grants. Existing BloodHound
imports may retain old `GH_EnterpriseTeam_<enterprise>_<id>` and projected
`GH_Team_<organization>_<ET_id>` nodes and their edges. Remove those old imports
or rebuild the affected graph using your deployment's supported cleanup process
before evaluating the new identity model; a new import alone does not guarantee
removal. Ordinary organization team IDs are unchanged.
