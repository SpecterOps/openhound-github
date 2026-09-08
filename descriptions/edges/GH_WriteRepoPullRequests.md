# GH_WriteRepoPullRequests

## General Information

The non-traversable GH_WriteRepoPullRequests edge represents a role's ability to create and merge pull requests in the repository. This permission is available to Write, Maintain, and Admin roles. Pull request merge access is security-significant because merging code into protected branches is a common vector for introducing unauthorized changes; however, actual merge capability on protected branches is further governed by branch protection rules and required reviews.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_RepoRole` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_WriteRepoPullRequests| n1
```
