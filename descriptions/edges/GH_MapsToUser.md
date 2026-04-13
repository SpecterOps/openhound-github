## General Information

The non-traversable `GH_MapsToUser` edge maps an external identity (provisioned via SAML or SCIM) to a GitHub user within the organization, or to an external IdP user (such as AZUser, OktaUser, or PingOneUser) in hybrid graph scenarios. It is created by `Git-HoundGraphQlSamlProvider` for SAML-linked identities and `Git-HoundScimUser` for SCIM-provisioned identities. This edge represents identity correlation rather than an attack path, connecting a user's external IdP account to their GitHub account for visibility into federated identity mappings.
