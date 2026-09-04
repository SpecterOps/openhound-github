# GH_PersonalAccessTokenRequest

## General Information

Represents a pending request from an organization member to access organization resources with a fine-grained personal access token. PAT requests are linked to their owning user and the organization. The requested permissions are captured as a JSON string in the properties.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `token_name` | `string` | The user-assigned display name of the token. |
| `owner_login` | `string` | The login handle of the user who submitted the request. |
| `repository_selection` | `string` | Whether the request targets `all`, `subset`, or `none` of the organization's repositories. |
| `reason` | `string` | The rationale provided by the requester for the access request. |
| `org_name` | `string` | The org name property. |
| `query_organization_permissions` | `string` | Query for organization permissions. |
| `query_user` | `string` | Query for user. |
| `query_repositories` | `string` | Query for repositories. |

## Diagram

```mermaid
graph LR
    n0["GH_Organization"]
    n1["GH_PersonalAccessTokenRequest"]
    n2["GH_User"]
    n0 -.->|GH_Contains| n1
    n2 -.->|GH_HasPersonalAccessTokenRequest| n1
```
