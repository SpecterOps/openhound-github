# GH_ToggleDiscussionAnswer

## General Information

The non-traversable GH_ToggleDiscussionAnswer edge represents a role's ability to mark or unmark a discussion comment as the accepted answer. This permission is available to Triage, Write, Maintain, and Admin roles and custom roles that have been granted this specific permission.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_ToggleDiscussionAnswer| n1
```
