# GH_HasRole

## General Information

The traversable GH_HasRole edge represents the assignment of a user or team to a specific role within the organization, repository, or team. This is the primary edge for connecting identities to their permissions and serves as the foundation of all access paths in the GitHub permission model. Because role assignment is the starting point for determining what a principal can do, this edge is traversable and critical for attack path analysis.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseTeam` | `GH_EnterpriseRole` | `true` |
| `GH_Team` | `GH_OrgRole` | `true` |
| `GH_Team` | `GH_RepoRole` | `true` |
| `GH_User` | `GH_EnterpriseRole` | `true` |
| `GH_User` | `GH_OrgRole` | `true` |
| `GH_User` | `GH_RepoRole` | `true` |
| `GH_User` | `GH_TeamRole` | `true` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseTeam"]
    n1["GH_EnterpriseRole"]
    n2["GH_Team"]
    n3["GH_OrgRole"]
    n4["GH_RepoRole"]
    n5["GH_User"]
    n6["GH_TeamRole"]
    n0 -->|GH_HasRole| n1
    n2 -->|GH_HasRole| n3
    n2 -->|GH_HasRole| n4
    n5 -->|GH_HasRole| n1
    n5 -->|GH_HasRole| n3
    n5 -->|GH_HasRole| n4
    n5 -->|GH_HasRole| n6
```
