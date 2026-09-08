# GH_HasPersonalAccessToken

## General Information

The non-traversable GH_HasPersonalAccessToken edge represents the relationship between a user and their fine-grained personal access tokens that have been granted access to the organization. This edge links each approved token back to the user who created it. Fine-grained personal access tokens are security-significant because they provide programmatic access to organization resources with specific scoped permissions. Tracking token ownership is essential for understanding which users have standing API access and for identifying tokens that may need revocation.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_User` | `GH_PersonalAccessToken` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_User"]
    n1["GH_PersonalAccessToken"]
    n0 -.->|GH_HasPersonalAccessToken| n1
```
