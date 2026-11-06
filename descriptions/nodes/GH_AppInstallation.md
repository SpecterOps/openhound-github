# GH_AppInstallation

## General Information

Represents a GitHub App installed on an organization or enterprise. Organization app installations have specific permissions and can be scoped to all repositories or a selection of repositories. The permissions granted to the installation are stored as `scope:access` values such as `contents:write` in the `permissions` property.

Unlike fine-grained personal access tokens, GitHub does not expose separate organization and repository permission buckets for app installations, so this property remains a single flat permission list.

Each installation is linked to its parent GH_App via a GH_InstalledAs edge. Organization installations with `repository_selection` set to `all` use one GH_CanAccess edge to the organization's repository/all GH_Scope; GH_ScopedTo edges enumerate the repositories in that reusable scope. For installations with `repository_selection` set to `selected`, the collector uses the enterprise organization-installation repositories API to enumerate the granted repositories when the enterprise installation has `Enterprise organization installations: read` or `Enterprise organization installation repositories: read`. If that permission is unavailable, selected repository edges are skipped.

Enterprise collection includes the authenticating collector app's installation, fetched independently of authentication discovery with `GET /enterprises/{enterprise}/installation`. It records granted enterprise permissions, timestamps, and suspension status, and is contained by `GH_Enterprise`. This is not a complete inventory of apps installed on the enterprise. Enterprise installations do not produce repository access edges. Parent app enrichment failures do not discard the installation.

`environment_slug` identifies the target account for both installation types. `target_type` distinguishes organization and enterprise targets. Older records using `org_login` or `enterprise_name` remain readable; these fields are no longer used for new installation context. Organization repository access is evaluated only for organization targets.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environment_slug` | `string` | The organization login or enterprise slug of the installation target. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `id` | `integer` | The GitHub installation ID. |
| `app_id` | `integer` | The GitHub App's numeric ID (shared across all installations of the same app). |
| `app_slug` | `string` | The app's URL-friendly slug identifier. |
| `description` | `string` | The app's description. |
| `html_url` | `string` | URL to the app's GitHub page. |
| `access_tokens_url` | `string` | API URL to create installation access tokens. |
| `repositories_url` | `string` | API URL to list repositories accessible to this installation. |
| `repository_selection` | `string` | Whether the app has access to `all` repositories or `selected` repositories. |
| `target_type` | `string` | The target type of the installation (e.g., `Organization` or `Enterprise`). |
| `permissions` | `list[string]` | Permissions granted to the installation in `scope:access` form. |
| `events` | `string` | JSON string of the webhook events the app subscribes to. |
| `created_at` | `datetime` | When the app was installed. |
| `updated_at` | `datetime` | When the installation was last updated. |
| `suspended_at` | `datetime` | When the installation was suspended, if applicable. |
| `environment_name` | `string` | The name of the environment (GitHub organization or enterprise) where the app is installed. |
| `query_repositories` | `string` | Query for repositories. |
| `query_app` | `string` | Query for app. |

## Diagram

```mermaid
graph LR
    n0["GH_App"]
    n1["GH_AppInstallation"]
    n2["GH_Repository"]
    n3["GH_Scope"]
    n4["GH_Organization"]
    n0 -->|GH_InstalledAs| n1
    n1 -.->|GH_CanAccess| n2
    n1 -.->|GH_CanAccess| n3
    n4 -.->|GH_Contains| n1
    n5["GH_Enterprise"]
    n5 -.->|GH_Contains| n1
```
