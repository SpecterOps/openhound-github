# GH_Repository

## General Information

Represents a GitHub repository within the organization. Repository nodes capture metadata about the repo including visibility, Actions enablement status, and security configuration. Repository role nodes (GH_RepoRole) are created alongside each repository to represent the permission levels available.

For repositories with active workflows, the collector records the applicable default workflow permissions and whether workflows may approve pull request reviews. These properties preserve the repository-level policy input later used to derive effective GITHUB_TOKEN permissions for GH_WorkflowJob nodes.

The `branch_count` and `environment_count` properties preserve GitHub-reported totals from the repository GraphQL response. These values can be compared to collected GH_Branch and GH_Environment children to identify incomplete collection before relying on branch- or environment-dependent analysis.

Every repository is linked from its organization's reusable repository/all GH_Scope. Private and internal repositories are also linked from repository/private_or_internal. This supports compact one- or two-hop access queries without repeating one GH_CanAccess edge per credential and repository.

Repositories also point to runner_group/all GH_Scope nodes through GH_IsEligibleFor; private and internal repositories additionally point to runner_group/private_or_internal. Those scopes enumerate canonical runner groups through GH_ScopedTo, while groups with arbitrary selected repository policies remain direct.

Organization secrets and variables with canonical all/private visibility are similarly reached through organization_secret and organization_variable scopes. Repository-owned, environment-owned, and arbitrarily selected organization assets remain direct targets.

Runner, secret, and variable boundary edges are emitted only when the organization has a matching canonical target, so empty scopes do not add per-repository edges.

## Diagram

```mermaid
graph LR
    n0["GH_AppInstallation"]
    n1["GH_Repository"]
    n2["GH_DeployKey"]
    n3["GH_Organization"]
    n4["GH_PersonalAccessToken"]
    n5["GH_RepoRole"]
    n6["GH_Branch"]
    n7["GH_BranchProtectionRule"]
    n8["GH_Environment"]
    n9["GH_OrgRunnerGroup"]
    n10["GH_OrgSecret"]
    n11["GH_OrgVariable"]
    n12["GH_RepoRunner"]
    n13["GH_RepoSecret"]
    n14["GH_RepoVariable"]
    n15["GH_Scope"]
    n16["GH_SecretScanningAlert"]
    n17["GH_Workflow"]
    n0 -.->|GH_CanAccess| n1
    n2 -.->|GH_CanAccess| n1
    n3 -->|GH_Owns| n1
    n4 -.->|GH_CanAccess| n1
    n5 -.->|GH_AddAssignee| n1
    n5 -.->|GH_AddLabel| n1
    n5 -->|GH_AdminTo| n1
    n5 -.->|GH_BypassBranchProtection| n1
    n5 -.->|GH_CanCreateBranch| n1
    n5 -->|GH_CanCreateEnvironment| n1
    n5 -->|GH_CanPwnRequest| n1
    n5 -.->|GH_CloseDiscussion| n1
    n5 -.->|GH_CloseIssue| n1
    n5 -.->|GH_ClosePullRequest| n1
    n5 -.->|GH_ConvertIssuesToDiscussions| n1
    n5 -.->|GH_CreateDiscussionCategory| n1
    n5 -.->|GH_CreateSoloMergeQueueEntry| n1
    n5 -.->|GH_CreateTag| n1
    n5 -.->|GH_DeleteAlertsCodeScanning| n1
    n5 -.->|GH_DeleteDiscussion| n1
    n5 -.->|GH_DeleteDiscussionComment| n1
    n5 -.->|GH_DeleteIssue| n1
    n5 -.->|GH_DeleteTag| n1
    n5 -.->|GH_EditCategoryOnDiscussion| n1
    n5 -.->|GH_EditDiscussionCategory| n1
    n5 -.->|GH_EditDiscussionComment| n1
    n5 -.->|GH_EditRepoAnnouncementBanners| n1
    n5 -.->|GH_EditRepoCustomPropertiesValues| n1
    n5 -.->|GH_EditRepoMetadata| n1
    n5 -.->|GH_EditRepoProtections| n1
    n5 -.->|GH_JumpMergeQueue| n1
    n5 -.->|GH_ManageDeployKeys| n1
    n5 -.->|GH_ManageDiscussionBadges| n1
    n5 -.->|GH_ManageRepoSecurityProducts| n1
    n5 -.->|GH_ManageSecurityProducts| n1
    n5 -.->|GH_ManageSettingsMergeTypes| n1
    n5 -.->|GH_ManageSettingsPages| n1
    n5 -.->|GH_ManageSettingsProjects| n1
    n5 -.->|GH_ManageSettingsWiki| n1
    n5 -.->|GH_ManageTopics| n1
    n5 -.->|GH_ManageWebhooks| n1
    n5 -.->|GH_MarkAsDuplicate| n1
    n5 -.->|GH_PushProtectedBranch| n1
    n5 -.->|GH_ReadCodeScanning| n1
    n5 -.->|GH_ReadRepoContents| n1
    n5 -.->|GH_RemoveAssignee| n1
    n5 -.->|GH_RemoveLabel| n1
    n5 -.->|GH_ReopenDiscussion| n1
    n5 -.->|GH_ReopenIssue| n1
    n5 -.->|GH_ReopenPullRequest| n1
    n5 -.->|GH_RequestPrReview| n1
    n5 -.->|GH_ResolveDependabotAlerts| n1
    n5 -.->|GH_ResolveSecretScanningAlerts| n1
    n5 -.->|GH_RunOrgMigration| n1
    n5 -.->|GH_SetInteractionLimits| n1
    n5 -.->|GH_SetIssueType| n1
    n5 -.->|GH_SetMilestone| n1
    n5 -.->|GH_SetSocialPreview| n1
    n5 -.->|GH_ToggleDiscussionAnswer| n1
    n5 -.->|GH_ToggleDiscussionCommentMinimize| n1
    n5 -.->|GH_ViewDependabotAlerts| n1
    n5 -.->|GH_ViewSecretScanningAlerts| n1
    n5 -.->|GH_WriteCodeScanning| n1
    n5 -.->|GH_WriteRepoContents| n1
    n5 -.->|GH_WriteRepoPullRequests| n1
    n1 -.->|GH_Contains| n6
    n1 -.->|GH_Contains| n7
    n1 -.->|GH_Contains| n2
    n1 -->|GH_CanDeployToEnvironment| n8
    n1 -.->|GH_Contains| n8
    n1 -->|GH_CanUseRunner| n9
    n1 -.->|GH_IsEligibleFor| n9
    n1 -->|GH_HasSecret| n10
    n1 -->|GH_HasVariable| n11
    n1 -.->|GH_CanUseRunner| n12
    n1 -.->|GH_Contains| n12
    n1 -.->|GH_Contains| n13
    n1 -->|GH_HasSecret| n13
    n1 -.->|GH_Contains| n14
    n1 -->|GH_HasVariable| n14
    n1 -->|GH_HasSecret| n15
    n1 -->|GH_HasVariable| n15
    n1 -.->|GH_IsEligibleFor| n15
    n1 -.->|GH_Contains| n16
    n1 -.->|GH_Contains| n17
    n15 -->|GH_ScopedTo| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
