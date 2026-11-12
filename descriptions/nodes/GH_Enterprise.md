# GH_Enterprise

## General Information

A GitHub Enterprise account that contains organizations, enterprise teams, roles, and managed users.

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_ClassicPersonalAccessToken"]
    n2["GH_EnterpriseManagedUser"]
    n3["GH_EnterpriseRole"]
    n4["GH_EnterpriseRunnerGroup"]
    n5["GH_EnterpriseTeam"]
    n6["GH_Organization"]
    n7["GH_SamlIdentityProvider"]
    n8["GH_User"]
    n0 -.->|GH_Contains| n1
    n0 -.->|GH_HasMember| n2
    n0 -.->|GH_Contains| n3
    n0 -.->|GH_Contains| n4
    n0 -.->|GH_Contains| n5
    n0 -.->|GH_Contains| n6
    n0 -.->|GH_HasSamlIdentityProvider| n7
    n0 -.->|GH_HasMember| n8
    n3 -.->|GH_CreateEnterpriseOrganizations| n0
    n3 -.->|GH_EditEnterpriseCustomPropertiesForOrganizations| n0
    n3 -->|GH_ManageEnterpriseAdmins| n0
    n3 -.->|GH_ManageEnterpriseIdentityProvider| n0
    n3 -->|GH_ManageEnterpriseMembers| n0
    n3 -->|GH_ManageEnterpriseOrganizationAdmins| n0
    n3 -.->|GH_ManageEnterpriseOrganizations| n0
    n3 -.->|GH_ManageEnterpriseReferrals| n0
    n3 -.->|GH_ManageEnterpriseTeams| n0
    n3 -.->|GH_ReadEnterpriseAuditLog| n0
    n3 -.->|GH_ReadEnterpriseDomainVerification| n0
    n3 -.->|GH_ReadEnterpriseMembers| n0
    n3 -.->|GH_ReadEnterpriseOrgProjects| n0
    n3 -.->|GH_ReadEnterpriseOrganizationAdmin| n0
    n3 -.->|GH_SetEnterpriseInteractionLimits| n0
    n3 -.->|GH_ViewEnterpriseActionsUsageMetrics| n0
    n3 -.->|GH_ViewEnterpriseBilling| n0
    n3 -.->|GH_ViewEnterpriseSecretScanningAlerts| n0
    n3 -.->|GH_WriteEnterpriseActionsPolicies| n0
    n3 -.->|GH_WriteEnterpriseBilling| n0
    n3 -.->|GH_WriteEnterprisePersonalAccessTokenPolicies| n0
    n3 -.->|GH_WriteEnterpriseSso| n0
    n3 -.->|GH_WriteEnterpriseTeamMembers| n0
```

## References

- [Enterprise roles](https://docs.github.com/en/enterprise-cloud@latest/rest/enterprise-admin/enterprise-roles)
