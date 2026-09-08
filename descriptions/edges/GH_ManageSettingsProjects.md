# GH_ManageSettingsProjects

## General Information

The non-traversable GH_ManageSettingsProjects edge represents a role's ability to manage project board settings on the repository. This permission is available to Maintain and Admin roles and custom roles that have been granted this specific permission.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_ManageSettingsProjects| n1
```
