# GH_ReadEnterpriseDomainVerification

## General Information

[Enterprise] Enterprise role can read domain verification data.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseRole` | `GH_Enterprise` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRole"]
    n1["GH_Enterprise"]
    n0 -.->|GH_ReadEnterpriseDomainVerification| n1
```
