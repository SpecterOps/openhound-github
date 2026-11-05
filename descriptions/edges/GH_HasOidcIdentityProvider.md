# GH_HasOidcIdentityProvider

## General Information

Links a GitHub Enterprise account to its configured OIDC identity provider.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_Enterprise` | `GH_OidcIdentityProvider` | `false` |

This relationship provides configuration context and does not itself represent an attack path.

## Diagram

```mermaid
graph LR
    enterprise["GH_Enterprise"] -.->|GH_HasOidcIdentityProvider| provider["GH_OidcIdentityProvider"]
```
