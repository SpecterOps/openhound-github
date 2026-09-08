# GH_ManageEnterpriseAdmins

## General Information

[Enterprise] Enterprise role can manage enterprise administrators.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseRole` | `GH_Enterprise` | `true` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRole"]
    n1["GH_Enterprise"]
    n0 -->|GH_ManageEnterpriseAdmins| n1
```
