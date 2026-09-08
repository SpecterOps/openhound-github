# GH_DeployKey

## General Information

A repository-scoped SSH deploy key that grants read-only or read-write access to repository contents.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `github_id` | `integer` | The numeric GitHub deploy key ID. |
| `title` | `string` | The user-assigned deploy key title. |
| `key` | `string` | The public SSH key material. |
| `verified` | `boolean` | Whether GitHub has verified the deploy key. |
| `enabled` | `boolean` | Whether the deploy key is currently enabled. |
| `read_only` | `boolean` | Whether the deploy key is restricted to read-only repository access. |
| `repository_permissions` | `list[string]` | Repository-scoped permissions in `scope:access` form. |
| `created_at` | `string` | When the deploy key was created. |
| `last_used` | `string` | When the deploy key was last used. |
| `added_by_login` | `string` | The login of the user who added the deploy key. |
| `added_by_id` | `string` | The node ID of the user who added the deploy key. |
| `repository_name` | `string` | The full name of the containing repository. |
| `repository_id` | `string` | The node_id of the containing repository. |
| `environment_name` | `string` | The name of the environment (GitHub organization). |
| `query_repository` | `string` | Query for the containing repository. |
| `query_added_by` | `string` | Query for the user who added the deploy key. |

## Diagram

```mermaid
graph LR
    n0["GH_DeployKey"]
    n1["GH_Repository"]
    n2["GH_User"]
    n0 -.->|GH_CanAccess| n1
    n1 -.->|GH_Contains| n0
    n2 -.->|GH_AddedDeployKey| n0
```
