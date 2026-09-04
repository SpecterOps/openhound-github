# GH_CanCreatePublicRepositories

## General Information

Role can create public repositories in the organization.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_OrgRole` | `GH_Organization` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n0 -.->|GH_CanCreatePublicRepositories| n1
```
