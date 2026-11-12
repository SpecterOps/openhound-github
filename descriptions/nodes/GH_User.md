# GH_User

## General Information

Represents a GitHub user who is a member of the organization. Users are associated with organization roles (Owner or Member) and can be assigned to repository roles and team roles.

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_User"]
    n2["GH_EnterpriseManagedUser"]
    n3["GH_ExternalIdentity"]
    n4["GH_SecretScanningAlert"]
    n5["GH_Branch"]
    n6["GH_BranchProtectionRule"]
    n7["GH_ClassicPersonalAccessToken"]
    n8["GH_DeployKey"]
    n9["GH_EnterpriseRole"]
    n10["GH_Environment"]
    n11["GH_OrgRole"]
    n12["GH_PersonalAccessToken"]
    n13["GH_PersonalAccessTokenRequest"]
    n14["GH_RepoRole"]
    n15["GH_TeamRole"]
    n0 -.->|GH_HasMember| n1
    n2 -.->|GH_MapsToUser| n1
    n3 -.->|GH_MapsToUser| n1
    n4 -->|GH_ValidToken| n1
    n1 -.->|GH_CanWriteBranch| n5
    n1 -.->|GH_BypassPullRequestAllowances| n6
    n1 -.->|GH_RestrictionsCanPush| n6
    n1 -.->|GH_HasPersonalAccessToken| n7
    n1 -.->|GH_AddedDeployKey| n8
    n1 -->|GH_HasRole| n9
    n1 -.->|GH_ApprovesDeploymentTo| n10
    n1 -->|GH_CanDeployToEnvironment| n10
    n1 -->|GH_HasRole| n11
    n1 -.->|GH_HasPersonalAccessToken| n12
    n1 -.->|GH_HasPersonalAccessTokenRequest| n13
    n1 -->|GH_HasRole| n14
    n1 -->|GH_HasRole| n15
```

## References

- [Organization roles](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/roles-in-an-organization)
