# GH_CanAccess

## General Information

The non-traversable GH_CanAccess edge indicates that a personal access token or app installation has been granted access to specific repositories. This edge represents the scope of access granted to a token or app rather than a direct attack path, providing visibility into which repositories are reachable through non-human credentials. It is non-traversable because token and app access does not transitively extend to other principals.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_AppInstallation` | `GH_Repository` | `false` |
| `GH_PersonalAccessToken` | `GH_Organization` | `false` |
| `GH_PersonalAccessToken` | `GH_Repository` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_AppInstallation"]
    n1["GH_Repository"]
    n2["GH_PersonalAccessToken"]
    n3["GH_Organization"]
    n0 -.->|GH_CanAccess| n1
    n2 -.->|GH_CanAccess| n3
    n2 -.->|GH_CanAccess| n1
```
