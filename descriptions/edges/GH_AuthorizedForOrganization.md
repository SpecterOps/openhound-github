# GH_AuthorizedForOrganization

## General Information

Classic personal access token has a recorded authorization for this organization.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_ClassicPersonalAccessToken` | `GH_Organization` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_ClassicPersonalAccessToken"]
    n1["GH_Organization"]
    n0 -.->|GH_AuthorizedForOrganization| n1
```
