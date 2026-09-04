# GH_CanCreateInternalRepositories

## General Information

Role can create internal repositories in the organization.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_OrgRole` | `GH_Organization` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n0 -.->|GH_CanCreateInternalRepositories| n1
```
