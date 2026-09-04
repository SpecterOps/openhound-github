# GH_EnterpriseRunner

## General Information

Represents a self-hosted runner owned at the GitHub Enterprise level. Enterprise runners are contained by GH_EnterpriseRunnerGroup nodes and exposed through GH_HasRunner. Repositories become eligible for the organization-facing runner group through GH_IsEligibleFor. Repositories and branches that can dispatch workflows then reach the runner through GH_CanUseRunner to an inherited GH_OrgRunnerGroup, GH_InheritedFrom to the enterprise group, and finally GH_HasRunner to the runner.

The node captures runner metadata such as operating system, status, busy state, labels, and whether the runner is ephemeral when GitHub returns that property.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `scope` | `string` | Whether the runner is enterprise, organization, or repository scoped. |
| `runner_id` | `integer` | The GitHub runner ID. |
| `os` | `string` | The runner operating system. |
| `status` | `string` | The runner status. |
| `busy` | `boolean` | Whether the runner is currently busy. |
| `ephemeral` | `boolean` | Whether the runner is ephemeral. |
| `labels` | `string` | JSON array of runner labels. |
| `runner_group_id` | `integer` | The associated runner group ID. |
| `runner_group_name` | `string` | The associated runner group name. |
| `runner_group_visibility` | `string` | Runner group visibility when organization scoped. |
| `repository_name` | `string` | The repository name for repository-scoped runners. |
| `repository_id` | `string` | The repository node_id for repository-scoped runners. |
| `repository_full_name` | `string` | The full repository name for repository-scoped runners. |
| `environment_name` | `string` | The name of the environment (GitHub organization). |
| `query_group` | `string` | Query for group. |
| `query_repositories` | `string` | Query for repositories. |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRunnerGroup"]
    n1["GH_EnterpriseRunner"]
    n0 -.->|GH_Contains| n1
    n0 -->|GH_HasRunner| n1
```
