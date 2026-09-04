# GH_ResolveSecretScanningAlerts

## General Information

The non-traversable GH_ResolveSecretScanningAlerts edge represents that a role can resolve (close) secret scanning alerts at the organization level. This edge is dynamically generated from custom organization role permissions discovered by the collector. Resolving a secret scanning alert marks a leaked secret as addressed, which removes it from active monitoring dashboards. An attacker with this permission could suppress alerts about leaked credentials to prevent incident response teams from detecting and rotating compromised secrets.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_OrgRole` | `GH_Organization` | `false` |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n2["GH_RepoRole"]
    n3["GH_Repository"]
    n0 -.->|GH_ResolveSecretScanningAlerts| n1
    n2 -.->|GH_ResolveSecretScanningAlerts| n3
```
