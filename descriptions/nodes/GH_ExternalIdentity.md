# GH_ExternalIdentity

## General Information

Represents an external identity collected through a SAML or OIDC provider, with a linked GitHub user when available. External identities map corporate user accounts (from providers like Okta, Azure AD, etc.) to GitHub user accounts, enabling single sign-on authentication. SAML attributes, SCIM attributes, and the linked user may be absent.

## Diagram

```mermaid
graph LR
    n0["GH_ExternalIdentity"]
    n1["GH_User"]
    n2["GH_SamlIdentityProvider"]
    n0 -.->|GH_MapsToUser| n1
    n2 -.->|GH_HasExternalIdentity| n0
```

## References

- [SAML single sign-on](https://docs.github.com/en/enterprise-cloud@latest/authentication/authenticating-with-single-sign-on/about-authentication-with-single-sign-on)
