# GH_HasOidcIdentityProvider

## General Information

Links a GitHub Enterprise account to its configured OIDC identity provider.

## Diagram

```mermaid
graph LR
    enterprise["GH_Enterprise"] -.->|GH_HasOidcIdentityProvider| provider["GH_OidcIdentityProvider"]
```

## References

- [SAML single sign-on](https://docs.github.com/en/enterprise-cloud@latest/authentication/authenticating-with-single-sign-on/about-authentication-with-single-sign-on)
- [Enterprise roles](https://docs.github.com/en/enterprise-cloud@latest/rest/enterprise-admin/enterprise-roles)
