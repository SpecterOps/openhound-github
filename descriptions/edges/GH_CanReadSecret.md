# GH_CanReadSecret

## General Information

Org role can read an organization secret by creating a repository in scope.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_OrgRole` | `GH_OrgSecret` | `true` |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_OrgSecret"]
    n0 -->|GH_CanReadSecret| n1
```
