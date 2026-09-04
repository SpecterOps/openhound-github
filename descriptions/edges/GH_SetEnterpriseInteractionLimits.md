# GH_SetEnterpriseInteractionLimits

## General Information

[Enterprise] Enterprise role can set interaction limits.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseRole` | `GH_Enterprise` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRole"]
    n1["GH_Enterprise"]
    n0 -.->|GH_SetEnterpriseInteractionLimits| n1
```
