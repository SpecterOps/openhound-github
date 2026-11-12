# GH_OidcIdentityProvider

## General Information

Represents an OIDC identity provider configured for a GitHub Enterprise account. Collection queries `enterprise.ownerInfo.oidcProvider` using the supplemental classic PAT. The PAT must belong to an enterprise owner and have `read:enterprise` access.

The node carries `GH_OidcIdentityProvider`, the shared secondary kind `GH_IdentityProvider`, and the source kind `GitHub`.

## Relationships

`GH_Enterprise` connects to this node through the non-traversable `GH_HasOidcIdentityProvider` relationship. Provider collection does not emit SAML service provider or SAML account relationships.

The provider connects to its `GH_ExternalIdentity` nodes through non-traversable `GH_HasExternalIdentity` edges. Those identities map to linked `GH_User` nodes through `GH_MapsToUser` when available.

## Diagram

```mermaid
graph LR
    enterprise["GH_Enterprise"] -.->|GH_HasOidcIdentityProvider| provider["GH_OidcIdentityProvider"]
    provider -.->|GH_HasExternalIdentity| identity["GH_ExternalIdentity"]
    identity -.->|GH_MapsToUser| user["GH_User"]
```

## References

- [Enterprise roles](https://docs.github.com/en/enterprise-cloud@latest/rest/enterprise-admin/enterprise-roles)
