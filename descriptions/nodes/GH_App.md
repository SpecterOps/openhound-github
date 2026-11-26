# GH_App

## General Information

Represents a GitHub App definition — the registered application entity. The app owner holds the private key that can generate installation access tokens for **every** GH_AppInstallation of this app. If the private key is compromised, all installations across all organizations and enterprises are affected.

App definitions are retrieved via `GET /apps/{app_slug}` after discovering app slugs from organization installations or the collector app's enterprise installation. Authenticated lookup can also retrieve private/internal apps where GitHub permits access. The `permissions_repository`, `permissions_organization`, `permissions_enterprise`, and `permissions_account` arrays record requested app permissions; each installation separately records its granted permissions. Unrecognized keys are retained in `permissions_unclassified`.

`registration_origin` classifies registration ownership using the collected inventory:

- `tenant_owned`: The owner is a collected organization or the collected enterprise.
- `member_owned`: The owner is a collected organization or enterprise member. The app remains owned by the user's account; membership does not imply tenant control or approval of the app.
- `third_party`: The owner is a user, organization, or enterprise without matching internal ownership or membership evidence. This is the default for recognized owners, including in organization-only collections; incomplete inventory can affect classification.
- `unknown`: Owner metadata is missing or its type is unsupported.

Organization membership is established from `membersWithRole`, and enterprise membership from the enterprise member inventory. Outside-collaborator status alone does not establish membership.

Incoming GH_CanManageApp edges expose account-wide management from the owning organization's or enterprise's qualifying predefined roles. These composed edges preserve role/account/ownership evidence. Per-App manager assignments are not currently enumerated, so the graph is not a complete inventory of registration managers.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environment_slug` | `string` | The organization login or enterprise slug where the app was collected. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `id` | `integer` | The GitHub App's numeric ID. |
| `client_id` | `string` | The app's OAuth client ID. |
| `slug` | `string` | The app's URL-friendly slug identifier. |
| `description` | `string` | The app's description. |
| `external_url` | `string` | The app's external homepage URL. |
| `html_url` | `string` | URL to the app's GitHub page. |
| `owner_login` | `string` | The login of the user or organization that owns the app. |
| `owner_node_id` | `string` | The node_id of the user or organization that owns the app. |
| `owner_type` | `string` | The type of the owner (e.g., `User`, `Organization`). |
| `permissions_repository` | `list[string]` | Requested repository permissions as `permission:access` values. |
| `permissions_organization` | `list[string]` | Requested organization permissions as `permission:access` values. |
| `permissions_enterprise` | `list[string]` | Requested enterprise permissions as `permission:access` values. |
| `permissions_account` | `list[string]` | Requested account permissions as `permission:access` values. |
| `permissions_unclassified` | `list[string]` | Requested permissions whose keys are absent from the scope mapping; preserved without guessing a scope. |
| `registration_origin` | `string` | `tenant_owned`, `member_owned`, `third_party`, or `unknown`, based on collected ownership and membership evidence. |
| `events` | `list[string]` | Default webhook events the app subscribes to. |
| `installations_count` | `integer` | The total number of installations of this app across all organizations. |
| `created_at` | `datetime` | When the app was created. |
| `updated_at` | `datetime` | When the app was last updated. |

## Diagram

```mermaid
graph LR
    n0["GH_App"]
    n1["GH_AppInstallation"]
    n2["GH_Enterprise"]
    n3["GH_Organization"]
    n4["GH_User"]
    n0 -->|GH_InstalledAs| n1
    n2 -->|GH_Owns| n0
    n3 -->|GH_Owns| n0
    n4 -->|GH_Owns| n0
```
