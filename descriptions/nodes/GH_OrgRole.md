# GH_OrgRole

## General Information

Represents an organization-level role such as Owner, Member, or a custom organization role. Org roles define what permissions a user or team has at the organization level. The Owner and Member roles are default (built-in), while custom roles inherit from a base role and can have additional permissions.

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_OrgRunnerGroup"]
    n2["GH_OrgSecret"]
    n3["GH_Organization"]
    n4["GH_Scope"]
    n5["GH_SecretScanningAlert"]
    n6["GH_Team"]
    n7["GH_User"]
    n0 -->|GH_HasBaseRole| n0
    n0 -->|GH_CanCreateRepositoryWithRunnerAccess| n1
    n0 -.->|GH_AddCollaborator| n3
    n0 -.->|GH_CanCreateInternalRepositories| n3
    n0 -.->|GH_CanCreatePrivateRepositories| n3
    n0 -.->|GH_CanCreatePublicRepositories| n3
    n0 -.->|GH_CanCreateRepositories| n3
    n0 -.->|GH_CreateTeam| n3
    n0 -.->|GH_InviteMember| n3
    n0 -.->|GH_ResolveSecretScanningAlerts| n3
    n0 -.->|GH_TransferRepository| n3
    n0 -.->|GH_ViewSecretScanningAlerts| n3
    n0 -->|GH_CanReadSecret| n4
    n4 -->|GH_ScopedTo| n2
    n0 -->|GH_CanReadSecretScanningAlert| n5
    n3 -.->|GH_Contains| n0
    n6 -->|GH_HasRole| n0
    n7 -->|GH_HasRole| n0
```

## References

- [Custom organization role API](https://docs.github.com/en/enterprise-cloud@latest/rest/orgs/organization-roles)
