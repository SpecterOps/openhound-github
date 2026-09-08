# GH_ExternalIdentity

## General Information

Represents an external identity from a SAML or SCIM identity provider that is linked to a GitHub user. External identities map corporate user accounts (from providers like Okta, Azure AD, etc.) to GitHub user accounts, enabling single sign-on authentication. Each external identity can have both SAML and SCIM identity attributes.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `guid` | `string` | The GUID of the external identity. |
| `saml_identity_username` | `string` | The username from the SAML identity. |
| `saml_identity_name_id` | `string` | The SAML NameID attribute. |
| `saml_identity_given_name` | `string` | The given name from the SAML identity. |
| `saml_identity_family_name` | `string` | The family name from the SAML identity. |
| `scim_identity_username` | `string` | The username from the SCIM identity. |
| `scim_identity_given_name` | `string` | The given name from the SCIM identity. |
| `scim_identity_family_name` | `string` | The family name from the SCIM identity. |
| `github_username` | `string` | The GitHub login of the linked user. |
| `github_user_id` | `string` | The GraphQL ID of the linked GitHub user. |
| `environment_name` | `string` | The name of the environment (GitHub organization or enterprise). |
| `query_mapped_users` | `string` | Query for mapped users. |

## Diagram

```mermaid
graph LR
    n0["GH_ExternalIdentity"]
    n1["GH_User"]
    n2["GH_SamlIdentityProvider"]
    n0 -.->|GH_MapsToUser| n1
    n2 -.->|GH_HasExternalIdentity| n0
```
