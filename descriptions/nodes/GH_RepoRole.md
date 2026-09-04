# GH_RepoRole

## General Information

Represents a repository-level permission role. Each repository has five default roles (Read, Write, Admin, Triage, Maintain) plus any custom repository roles defined at the organization level. Repo roles define what actions a user or team can perform on a specific repository. Default roles form an inheritance hierarchy (Triage -> Read, Maintain -> Write, Admin includes all), and custom roles inherit from one of the base roles.

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `name` | `string` | The node name used for matching and display. |
| `displayname` | `string` | The human-readable display name. |
| `environmentid` | `string` | The identifier of the GitHub environment where this node was collected. |
| `last_seen` | `datetime` | The timestamp when this node was last observed during collection. |
| `node_id` | `string` | The stable identifier used as the OpenGraph node ID; this is the native GitHub node ID where available. |
| `short_name` | `string` | The short role name (e.g., `read`, `write`, `admin`, `triage`, `maintain`, or custom role name). |
| `repository_name` | `string` | The name of the repository this role belongs to. |
| `repository_id` | `string` | The node_id of the repository this role belongs to. |
| `environment_name` | `string` | The name of the environment (GitHub organization). |
| `type` | `string` | `default` for built-in roles or `custom` for custom repository roles. |
| `query_explicit_users` | `string` | Query for explicit users. |
| `query_explicit_teams` | `string` | Query for explicit teams. |
| `query_unrolled_members` | `string` | Query for unrolled members. |
| `query_repository_permissions` | `string` | Query for repository permissions. |

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Branch"]
    n2["GH_Environment"]
    n3["GH_Repository"]
    n4["GH_SecretScanningAlert"]
    n5["GH_Team"]
    n6["GH_User"]
    n0 -.->|GH_CanEditProtection| n1
    n0 -->|GH_CanPwnRequest| n1
    n0 -.->|GH_CanWriteBranch| n1
    n0 -->|GH_CanDeployToEnvironment| n2
    n0 -->|GH_CanEditEnvironment| n2
    n0 -->|GH_HasBaseRole| n0
    n0 -.->|GH_AddAssignee| n3
    n0 -.->|GH_AddLabel| n3
    n0 -->|GH_AdminTo| n3
    n0 -.->|GH_BypassBranchProtection| n3
    n0 -.->|GH_CanCreateBranch| n3
    n0 -->|GH_CanCreateEnvironment| n3
    n0 -->|GH_CanPwnRequest| n3
    n0 -.->|GH_CloseDiscussion| n3
    n0 -.->|GH_CloseIssue| n3
    n0 -.->|GH_ClosePullRequest| n3
    n0 -.->|GH_ConvertIssuesToDiscussions| n3
    n0 -.->|GH_CreateDiscussionCategory| n3
    n0 -.->|GH_CreateSoloMergeQueueEntry| n3
    n0 -.->|GH_CreateTag| n3
    n0 -.->|GH_DeleteAlertsCodeScanning| n3
    n0 -.->|GH_DeleteDiscussion| n3
    n0 -.->|GH_DeleteDiscussionComment| n3
    n0 -.->|GH_DeleteIssue| n3
    n0 -.->|GH_DeleteTag| n3
    n0 -.->|GH_EditCategoryOnDiscussion| n3
    n0 -.->|GH_EditDiscussionCategory| n3
    n0 -.->|GH_EditDiscussionComment| n3
    n0 -.->|GH_EditRepoAnnouncementBanners| n3
    n0 -.->|GH_EditRepoCustomPropertiesValues| n3
    n0 -.->|GH_EditRepoMetadata| n3
    n0 -.->|GH_EditRepoProtections| n3
    n0 -.->|GH_JumpMergeQueue| n3
    n0 -.->|GH_ManageDeployKeys| n3
    n0 -.->|GH_ManageDiscussionBadges| n3
    n0 -.->|GH_ManageRepoSecurityProducts| n3
    n0 -.->|GH_ManageSecurityProducts| n3
    n0 -.->|GH_ManageSettingsMergeTypes| n3
    n0 -.->|GH_ManageSettingsPages| n3
    n0 -.->|GH_ManageSettingsProjects| n3
    n0 -.->|GH_ManageSettingsWiki| n3
    n0 -.->|GH_ManageTopics| n3
    n0 -.->|GH_ManageWebhooks| n3
    n0 -.->|GH_MarkAsDuplicate| n3
    n0 -.->|GH_PushProtectedBranch| n3
    n0 -.->|GH_ReadCodeScanning| n3
    n0 -.->|GH_ReadRepoContents| n3
    n0 -.->|GH_RemoveAssignee| n3
    n0 -.->|GH_RemoveLabel| n3
    n0 -.->|GH_ReopenDiscussion| n3
    n0 -.->|GH_ReopenIssue| n3
    n0 -.->|GH_ReopenPullRequest| n3
    n0 -.->|GH_RequestPrReview| n3
    n0 -.->|GH_ResolveDependabotAlerts| n3
    n0 -.->|GH_ResolveSecretScanningAlerts| n3
    n0 -.->|GH_RunOrgMigration| n3
    n0 -.->|GH_SetInteractionLimits| n3
    n0 -.->|GH_SetIssueType| n3
    n0 -.->|GH_SetMilestone| n3
    n0 -.->|GH_SetSocialPreview| n3
    n0 -.->|GH_ToggleDiscussionAnswer| n3
    n0 -.->|GH_ToggleDiscussionCommentMinimize| n3
    n0 -.->|GH_ViewDependabotAlerts| n3
    n0 -.->|GH_ViewSecretScanningAlerts| n3
    n0 -.->|GH_WriteCodeScanning| n3
    n0 -.->|GH_WriteRepoContents| n3
    n0 -.->|GH_WriteRepoPullRequests| n3
    n0 -->|GH_CanReadSecretScanningAlert| n4
    n5 -->|GH_HasRole| n0
    n6 -->|GH_HasRole| n0
```
