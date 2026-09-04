# GH_ManageEnterpriseOrganizations

## General Information

[Enterprise] Enterprise role can manage organizations.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseRole` | `GH_Enterprise` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRole"]
    n1["GH_Enterprise"]
    n0 -.->|GH_ManageEnterpriseOrganizations| n1
```
