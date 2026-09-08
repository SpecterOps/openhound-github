# GH_ViewEnterpriseSecretScanningAlerts

## General Information

[Enterprise] Enterprise role can view secret-scanning alerts.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_EnterpriseRole` | `GH_Enterprise` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseRole"]
    n1["GH_Enterprise"]
    n0 -.->|GH_ViewEnterpriseSecretScanningAlerts| n1
```
