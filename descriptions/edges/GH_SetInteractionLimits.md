# GH_SetInteractionLimits

## General Information

The non-traversable GH_SetInteractionLimits edge represents a role's ability to set temporary interaction limits to restrict who can comment, open issues, or create pull requests. This permission is available to Maintain and Admin roles and custom roles that have been granted this specific permission.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_SetInteractionLimits| n1
```
