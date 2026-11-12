# GH_Organization

## General Information

Represents a GitHub organization. This is the organization-scoped administrative root for its collected repositories, teams, roles and configuration; enterprise-scoped resources have their own root. Organization-level settings such as default repository permissions, Actions configuration, and security features are captured as properties on this node.

## Diagram

```mermaid
graph LR
    n0["GH_ClassicPersonalAccessToken"]
    n1["GH_Organization"]
    n2["GH_Enterprise"]
    n3["GH_EnterpriseTeam"]
    n4["GH_OrgRole"]
    n5["GH_AppInstallation"]
    n6["GH_OrgRunnerGroup"]
    n7["GH_OrgSecret"]
    n8["GH_OrgVariable"]
    n9["GH_PersonalAccessToken"]
    n10["GH_PersonalAccessTokenRequest"]
    n11["GH_Repository"]
    n12["GH_SamlIdentityProvider"]
    n13["GH_SecretScanningAlert"]
    n14["GH_Scope"]
    n0 -.->|GH_AuthorizedForOrganization| n1
    n2 -.->|GH_Contains| n1
    n3 -.->|GH_AssignedTo| n1
    n4 -.->|GH_AddCollaborator| n1
    n4 -.->|GH_CanCreateInternalRepositories| n1
    n4 -.->|GH_CanCreatePrivateRepositories| n1
    n4 -.->|GH_CanCreatePublicRepositories| n1
    n4 -.->|GH_CanCreateRepositories| n1
    n4 -.->|GH_CreateTeam| n1
    n4 -.->|GH_InviteMember| n1
    n4 -.->|GH_ResolveSecretScanningAlerts| n1
    n4 -.->|GH_TransferRepository| n1
    n4 -.->|GH_ViewSecretScanningAlerts| n1
    n1 -.->|GH_Contains| n5
    n1 -.->|GH_Contains| n4
    n1 -.->|GH_Contains| n6
    n1 -.->|GH_Contains| n7
    n1 -.->|GH_Contains| n8
    n1 -.->|GH_Contains| n9
    n1 -.->|GH_Contains| n10
    n1 -->|GH_Owns| n11
    n1 -.->|GH_HasSamlIdentityProvider| n12
    n1 -.->|GH_Contains| n13
    n1 -.->|GH_Contains| n14
    n9 -.->|GH_CanAccess| n1
```

## References

- [Organization roles](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/roles-in-an-organization)
