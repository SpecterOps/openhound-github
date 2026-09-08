# GH_RepoVariable

## General Information

Represents a repository-level GitHub Actions variable. These are variables defined directly on a specific repository and are only accessible to workflows running in that repository. Unlike secrets, variable values are readable via the API.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `repository_name` | `string` | The name of the containing repository. |
| `repository_id` | `string` | The node_id of the containing repository. |
| `environment_name` | `string` | The name of the environment (GitHub organization). |
| `value` | `string` | The plaintext value of the variable. |
| `created_at` | `string` | When the variable was created. |
| `updated_at` | `string` | When the variable was last updated. |
| `query_visible_repositories` | `string` | Query for visible repositories. |

## Diagram

```mermaid
graph LR
    n0["GH_Repository"]
    n1["GH_RepoVariable"]
    n2["GH_WorkflowJob"]
    n3["GH_WorkflowStep"]
    n0 -.->|GH_Contains| n1
    n0 -->|GH_HasVariable| n1
    n2 -.->|GH_UsesVariable| n1
    n3 -.->|GH_UsesVariable| n1
```
