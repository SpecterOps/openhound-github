# GH_MarkAsDuplicate

## General Information

The non-traversable GH_MarkAsDuplicate edge represents a role's ability to mark issues or pull requests as duplicates. This permission is available to Triage, Write, Maintain, and Admin roles and custom roles that have been granted this specific permission.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_MarkAsDuplicate| n1
```
