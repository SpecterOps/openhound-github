# GH_ResolveDependabotAlerts

## General Information

The non-traversable GH_ResolveDependabotAlerts edge represents a role's ability to dismiss or resolve Dependabot alerts. This permission is available to Write, Maintain, and Admin roles and custom roles that have been granted this specific permission. An attacker could dismiss valid alerts to suppress vulnerability warnings and prevent remediation.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_ResolveDependabotAlerts| n1
```
