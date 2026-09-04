# GH_ReadEnterpriseOrganizationAdmin

## General Information

[Enterprise] Enterprise role can read organization administration data.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseRole` | `GH_Enterprise` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRole"]
    n1["GH_Enterprise"]
    n0 -.->|GH_ReadEnterpriseOrganizationAdmin| n1
```
