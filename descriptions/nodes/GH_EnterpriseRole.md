# GH_EnterpriseRole

## General Information

The role a user or team has at the GitHub Enterprise level.

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_EnterpriseRole"]
    n2["GH_EnterpriseTeam"]
    n3["GH_User"]
    n0 -.->|GH_Contains| n1
    n1 -.->|GH_CreateEnterpriseOrganizations| n0
    n1 -.->|GH_EditEnterpriseCustomPropertiesForOrganizations| n0
    n1 -->|GH_ManageEnterpriseAdmins| n0
    n1 -.->|GH_ManageEnterpriseIdentityProvider| n0
    n1 -->|GH_ManageEnterpriseMembers| n0
    n1 -->|GH_ManageEnterpriseOrganizationAdmins| n0
    n1 -.->|GH_ManageEnterpriseOrganizations| n0
    n1 -.->|GH_ManageEnterpriseReferrals| n0
    n1 -.->|GH_ManageEnterpriseTeams| n0
    n1 -.->|GH_ReadEnterpriseAuditLog| n0
    n1 -.->|GH_ReadEnterpriseDomainVerification| n0
    n1 -.->|GH_ReadEnterpriseMembers| n0
    n1 -.->|GH_ReadEnterpriseOrgProjects| n0
    n1 -.->|GH_ReadEnterpriseOrganizationAdmin| n0
    n1 -.->|GH_SetEnterpriseInteractionLimits| n0
    n1 -.->|GH_ViewEnterpriseActionsUsageMetrics| n0
    n1 -.->|GH_ViewEnterpriseBilling| n0
    n1 -.->|GH_ViewEnterpriseSecretScanningAlerts| n0
    n1 -.->|GH_WriteEnterpriseActionsPolicies| n0
    n1 -.->|GH_WriteEnterpriseBilling| n0
    n1 -.->|GH_WriteEnterprisePersonalAccessTokenPolicies| n0
    n1 -.->|GH_WriteEnterpriseSso| n0
    n1 -.->|GH_WriteEnterpriseTeamMembers| n0
    n2 -->|GH_HasRole| n1
    n3 -->|GH_HasRole| n1
```

## References

- [Enterprise roles](https://docs.github.com/en/enterprise-cloud@latest/rest/enterprise-admin/enterprise-roles)
