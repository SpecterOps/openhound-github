# GH_ManageEnterpriseIdentityProvider

## General Information

[Enterprise] Enterprise role can manage the enterprise identity provider.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseRole` | `GH_Enterprise` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRole"]
    n1["GH_Enterprise"]
    n0 -.->|GH_ManageEnterpriseIdentityProvider| n1
```
