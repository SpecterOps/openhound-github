# Generic
CONTAINS = "GH_Contains"
ASSIGNED_TO = "GH_AssignedTo"

# Administrative edges
ADMIN_TO = "GH_AdminTo"
OWNS = "GH_Owns"

# Role and permission edges
HAS_MEMBER = "GH_HasMember"
HAS_ROLE = "GH_HasRole"
HAS_BASE_ROLE = "GH_HasBaseRole"
ADD_MEMBER = "GH_AddMember"
MEMBER_OF = "GH_MemberOf"

# Access and capability edges
CAN_ACCESS = "GH_CanAccess"
CAN_USE_RUNNER = "GH_CanUseRunner"
CAN_CREATE_BRANCH = "GH_CanCreateBranch"
CAN_EDIT_PROTECTION = "GH_CanEditProtection"
CAN_WRITE_BRANCH = "GH_CanWriteBranch"
READ_REPO_CONTENTS = "GH_ReadRepoContents"
WRITE_REPO_CONTENTS = "GH_WriteRepoContents"
WRITE_REPO_PULL_REQUESTS = "GH_WriteRepoPullRequests"

# Branch and protection edges
HAS_BRANCH = "GH_HasBranch"
PROTECTED_BY = "GH_ProtectedBy"
BYPASS_PULL_REQUEST_ALLOWANCES = "GH_BypassPullRequestAllowances"
RESTRICTIONS_CAN_PUSH = "GH_RestrictionsCanPush"

# Identity and authentication edges
HAS_EXTERNAL_IDENTITY = "GH_HasExternalIdentity"
HAS_SAML_IDENTITY_PROVIDER = "GH_HasSamlIdentityProvider"
MAPS_TO_USER = "GH_MapsToUser"
SYNCED_TO_GH_USER = "GH_SyncedTo"

# Personal access token edges
HAS_PERSONAL_ACCESS_TOKEN = "GH_HasPersonalAccessToken"
HAS_PERSONAL_ACCESS_TOKEN_REQUEST = "GH_HasPersonalAccessTokenRequest"

# Secret and variable edges
HAS_SECRET = "GH_HasSecret"
HAS_VARIABLE = "GH_HasVariable"

# App installation edges
INSTALLED_AS = "GH_InstalledAs"

# Other
HAS_SECRET_SCANNING_ALERT = "GH_HasSecretScanningAlert"
VALID_TOKEN = "GH_ValidToken"
HAS_WORKFLOW = "GH_HasWorkflow"
HAS_ENVIRONMENT = "GH_HasEnvironment"


INVITE_MEMBER = "GH_InviteMember"
ADD_COLLABORATOR = "GH_AddCollaborator"
CREATE_REPOSITORY = "GH_CreateRepository"
CREATE_TEAM = "GH_CreateTeam"
TRANSFER_REPOSITORY = "GH_TransferRepository"


# Defaults for reviewer
ADD_LABEL = "GH_AddLabel"
REMOVE_LABEL = "GH_RemoveLabel"
CLOSE_ISSUE = "GH_CloseIssue"
REOPEN_ISSUE = "GH_ReopenIssue"
CLOSE_PR = "GH_ClosePullRequest"
REOPEN_PR = "GH_ReopenPullRequest"
ADD_ASSIGNEE = "GH_AddAssignee"
REMOVE_ASSIGNEE = "GH_RemoveAssignee"
REQUEST_PR_REVIEW = "GH_RequestPrReview"
MARK_AS_DUPLICATE = "GH_MarkAsDuplicate"
SET_MILESTONE = "GH_SetMilestone"
SET_ISSUE_TYPE = "GH_SetIssueType"
DELETE_DISCUSSION = "GH_DeleteDiscussion"
TOGGLE_DISCUSSION_ANSWER = "GH_ToggleDiscussionAnswer"
TOGGLE_DISCUSSION_COMMENT_MINIMIZE = "GH_ToggleDiscussionCommentMinimize"
EDIT_DISCUSSION_CATEGORY = "GH_EditDiscussionCategory"
CREATE_DISCUSSION_CATEGORY = "GH_CreateDiscussionCategory"
CONVERT_ISSUES_TO_DISCUSSIONS = "GH_ConvertIssuesToDiscussions"
CLOSE_DISCUSSION = "GH_CloseDiscussion"
REOPEN_DISCUSSION = "GH_ReopenDiscussion"
EDIT_CATEGORY_ON_DISCUSSION = "GH_EditCategoryOnDiscussion"
EDIT_DISCUSSION_COMMENT = "GH_EditDiscussionComment"
DELETE_DISCUSSION_COMMENT = "GH_DeleteDiscussionComment"

# And mooore
READ_CODE_SCANNING = "GH_ReadCodeScanning"
WRITE_CODE_SCANNING = "GH_WriteCodeScanning"
VIEW_DEPENDABOT_ALERTS = "GH_ViewDependabotAlerts"
RESOLVE_DEPENDABOT_ALERTS = "GH_ResolveDependabotAlerts"
MANAGE_DISCUSSION_BADGES = "GH_ManageDiscussionBadges"


# More maintainer edges
MANAGE_TOPICS = "GH_ManageTopics"
MANAGE_WIKI_SETTINGS = "GH_ManageSettingsWiki"
MANAGE_PROJECTS_SETTINGS = "GH_ManageSettingsProjects"
MANAGE_MERGE_TYPES_SETTINGS = "GH_ManageSettingsMergeTypes"
MANAGE_PAGES_SETTINGS = "GH_ManageSettingsPages"
EDIT_REPO_METADATA = "GH_EditRepoMetadata"
SET_INTERACTION_LIMITS = "GH_SetInteractionLimits"
SET_SOCIAL_PREVIEW = "GH_SetSocialPreview"
CREATE_TAG = "GH_CreateTag"
EDIT_REPO_ANNOUNCEMENT_BANNERS = "GH_EditRepoAnnouncementBanners"

DELETE_ISSUE = "GH_DeleteIssue"
DELETE_TAG = "GH_DeleteTag"
RESOLVE_SECRET_SCANNING_ALERTS = "GH_ResolveSecretScanningAlerts"


MANAGE_WEBHOOKS = "GH_ManageWebhooks"
MANAGE_DEPLOY_KEYS = "GH_ManageDeployKeys"
BYPASS_BRANCH_PROTECTION = "GH_BypassBranchProtection"
PUSH_PROTECTED_BRANCH = "GH_PushProtectedBranch"
DELETE_ALERTS_CODE_SCANNING = "GH_DeleteAlertsCodeScanning"
VIEW_SECRET_SCANNING_ALERTS = "GH_ViewSecretScanningAlerts"
RUN_ORG_MIGRATION = "GH_RunOrgMigration"
MANAGE_SECURITY_PRODUCTS = "GH_ManageSecurityProducts"
MANAGE_REPO_SECURITY_PRODUCTS = "GH_ManageRepoSecurityProducts"
EDIT_REPO_PROTECTIONS = "GH_EditRepoProtections"
JUMP_MERGE_QUEUE = "GH_JumpMergeQueue"
CREATE_SOLO_MERGE_QUEUE_ENTRY = "GH_CreateSoloMergeQueueEntry"
EDIT_REPO_CUSTOM_PROPERTIES_VALUES = "GH_EditRepoCustomPropertiesValues"

READ_REPO_PULL_REQUEST = "GH_ReadRepoPullRequests"
MANAGE_DISCUSSION_SPOTLIGHTS = "GH_ManageDiscussionSpotlights"
