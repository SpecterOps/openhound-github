# GH_Enterprise

## General Information

A GitHub Enterprise account that contains organizations, enterprise teams, roles, and managed users.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `collected` | `boolean` | Whether this node was collected directly. |
| `slug` | `string` | The enterprise slug. |
| `enterprise_name` | `string` | The enterprise display name. |
| `description` | `string` | The enterprise description. |
| `location` | `string` | The enterprise location. |
| `url` | `string` | The enterprise GitHub URL. |
| `website_url` | `string` | The enterprise website URL. |
| `created_at` | `string` | When the enterprise was created. |
| `updated_at` | `string` | When the enterprise was last updated. |
| `billing_email` | `string` | The enterprise billing email. |
| `security_contact_email` | `string` | The enterprise security contact email. |
| `viewer_is_admin` | `boolean` | Whether the authenticated viewer is an enterprise admin. |
| `environment_name` | `string` | The enterprise environment name. |
| `query_organizations` | `string` | Query for contained organizations. |

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_EnterpriseManagedUser"]
    n2["GH_EnterpriseRole"]
    n3["GH_EnterpriseRunnerGroup"]
    n4["GH_EnterpriseTeam"]
    n5["GH_Organization"]
    n6["GH_SamlIdentityProvider"]
    n7["GH_User"]
    n0 -.->|GH_HasMember| n1
    n0 -.->|GH_Contains| n2
    n0 -.->|GH_Contains| n3
    n0 -.->|GH_Contains| n4
    n0 -.->|GH_Contains| n5
    n0 -.->|GH_HasSamlIdentityProvider| n6
    n0 -.->|GH_HasMember| n7
    n2 -.->|GH_CreateEnterpriseOrganizations| n0
    n2 -.->|GH_EditEnterpriseCustomPropertiesForOrganizations| n0
    n2 -->|GH_ManageEnterpriseAdmins| n0
    n2 -.->|GH_ManageEnterpriseIdentityProvider| n0
    n2 -->|GH_ManageEnterpriseMembers| n0
    n2 -->|GH_ManageEnterpriseOrganizationAdmins| n0
    n2 -.->|GH_ManageEnterpriseOrganizations| n0
    n2 -.->|GH_ManageEnterpriseReferrals| n0
    n2 -.->|GH_ManageEnterpriseTeams| n0
    n2 -.->|GH_ReadEnterpriseAuditLog| n0
    n2 -.->|GH_ReadEnterpriseDomainVerification| n0
    n2 -.->|GH_ReadEnterpriseMembers| n0
    n2 -.->|GH_ReadEnterpriseOrgProjects| n0
    n2 -.->|GH_ReadEnterpriseOrganizationAdmin| n0
    n2 -.->|GH_SetEnterpriseInteractionLimits| n0
    n2 -.->|GH_ViewEnterpriseActionsUsageMetrics| n0
    n2 -.->|GH_ViewEnterpriseBilling| n0
    n2 -.->|GH_ViewEnterpriseSecretScanningAlerts| n0
    n2 -.->|GH_WriteEnterpriseActionsPolicies| n0
    n2 -.->|GH_WriteEnterpriseBilling| n0
    n2 -.->|GH_WriteEnterprisePersonalAccessTokenPolicies| n0
    n2 -.->|GH_WriteEnterpriseSso| n0
    n2 -.->|GH_WriteEnterpriseTeamMembers| n0
```
