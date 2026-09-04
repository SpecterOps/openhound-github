# GH_WriteEnterpriseTeamMembers

## General Information

[Enterprise] Enterprise role can write enterprise team membership.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseRole` | `GH_Enterprise` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRole"]
    n1["GH_Enterprise"]
    n0 -.->|GH_WriteEnterpriseTeamMembers| n1
```
