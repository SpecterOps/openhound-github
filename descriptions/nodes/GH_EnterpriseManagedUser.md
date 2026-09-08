# GH_EnterpriseManagedUser

## General Information

A GitHub Enterprise managed user account linked to an enterprise identity provider.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `login` | `string` | The managed user login. |
| `full_name` | `string` | The managed user display name. |
| `url` | `string` | The managed user URL. |
| `created_at` | `string` | When the managed user was created. |
| `updated_at` | `string` | When the managed user was last updated. |
| `github_user_id` | `string` | The backing GitHub user ID. |
| `github_username` | `string` | The backing GitHub username. |
| `environment_name` | `string` | The enterprise environment name. |
| `query_enterprises` | `string` | Query for enterprises containing this managed user. |
| `query_mapped_user` | `string` | Query for the backing GitHub user. |

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_EnterpriseManagedUser"]
    n2["GH_User"]
    n0 -.->|GH_HasMember| n1
    n1 -.->|GH_MapsToUser| n2
```
