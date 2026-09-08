# GH_OrgVariable

## General Information

Represents an organization-level GitHub Actions variable. Organization variables can be scoped to all repositories, only private/internal repositories, or a specific set of selected repositories. The visibility property determines how GH_HasVariable edges are resolved to repository nodes. Unlike secrets, variable values are readable via the API.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `visibility` | `string` | The variable's visibility scope: `all` (all repos), `private` (private and internal repos), or `selected` (specific repos). |
| `environment_name` | `string` | The name of the environment (GitHub organization). |
| `value` | `string` | The plaintext value of the variable. |
| `created_at` | `string` | When the variable was created. |
| `updated_at` | `string` | When the variable was last updated. |
| `query_visible_repositories` | `string` | Query for visible repositories. |

## Diagram

```mermaid
graph LR
    n0["GH_Organization"]
    n1["GH_OrgVariable"]
    n2["GH_Repository"]
    n3["GH_WorkflowJob"]
    n4["GH_WorkflowStep"]
    n0 -.->|GH_Contains| n1
    n2 -->|GH_HasVariable| n1
    n3 -.->|GH_UsesVariable| n1
    n4 -.->|GH_UsesVariable| n1
```
