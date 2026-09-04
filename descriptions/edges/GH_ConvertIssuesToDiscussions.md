# GH_ConvertIssuesToDiscussions

## General Information

The non-traversable GH_ConvertIssuesToDiscussions edge represents a role's ability to convert issues to discussions, moving them from the issue tracker to the discussions forum. This permission is available to Triage, Write, Maintain, and Admin roles and custom roles that have been granted this specific permission.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_ConvertIssuesToDiscussions| n1
```
