# GH_EnterpriseTeam

## General Information

A team managed at the GitHub Enterprise level and assignable across organizations. One native `ET_` identity is retained across organization contexts; repository permissions attach directly to the enterprise team.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The native GitHub `ET_` identifier used as the OpenGraph node ID. Returned IDs take precedence; a validated MessagePack encoding is used when the enterprise endpoint omits the ID. |
| `github_team_id` | `string or integer` | The raw GitHub enterprise team ID. |
| `slug` | `string` | The enterprise team slug. |
| `projected_slug` | `string` | The organization-projected team slug. |
| `group_id` | `string` | The linked SCIM group ID. |
| `description` | `string` | The team description. |
| `created_at` | `string` | When the team was created. |
| `updated_at` | `string` | When the team was last updated. |
| `environment_name` | `string` | The enterprise environment name. |
| `query_enterprise` | `string` | Query for the containing enterprise. |
| `query_assigned_organizations` | `string` | Query for assigned organizations. |
| `query_repositories` | `string` | Query for repository roles and repositories. |
| `query_members` | `string` | Query for team members. |

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_EnterpriseTeam"]
    n2["GH_EnterpriseRole"]
    n3["GH_Organization"]
    n4["GH_RepoRole"]
    n5["GH_TeamRole"]
    n0 -.->|GH_Contains| n1
    n1 -->|GH_HasRole| n2
    n1 -.->|GH_AssignedTo| n3
    n1 -->|GH_HasRole| n4
    n5 -->|GH_MemberOf| n1
```
