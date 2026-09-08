# GH_AppInstallation

## General Information

Represents a GitHub App installed on an organization. App installations have specific permissions and can be scoped to all repositories or a selection of repositories. The permissions granted to the app are captured as a JSON string in the properties.

Each installation is linked to its parent GH_App via a GH_InstalledAs edge. For installations with `repository_selection` set to `all`, GH_CanAccess edges are created to every repository in the organization. For installations with `repository_selection` set to `selected`, repository-level edges cannot be enumerated with a PAT (requires app installation token authentication).

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
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
| `target_type` | `string` | The target type of the installation (e.g., `Organization`). |
| `permissions` | `string` | JSON string of the permissions granted to the app (e.g., `{"contents": "read", "metadata": "read"}`). |
| `events` | `string` | JSON string of the webhook events the app subscribes to. |
| `created_at` | `datetime` | When the app was installed. |
| `updated_at` | `datetime` | When the installation was last updated. |
| `suspended_at` | `datetime` | When the installation was suspended, if applicable. |
| `environment_name` | `string` | The name of the environment (GitHub organization) where the app is installed. |
| `query_repositories` | `string` | Query for repositories. |
| `query_app` | `string` | Query for app. |

## Diagram

```mermaid
graph LR
    n0["GH_App"]
    n1["GH_AppInstallation"]
    n2["GH_Repository"]
    n3["GH_Organization"]
    n0 -->|GH_InstalledAs| n1
    n1 -.->|GH_CanAccess| n2
    n3 -.->|GH_Contains| n1
```
