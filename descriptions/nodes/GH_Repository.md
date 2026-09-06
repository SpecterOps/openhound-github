## Description

Represents a GitHub repository within the organization. Repository nodes capture metadata about the repo including visibility, Actions enablement status, and security configuration. Repository role nodes (GH_RepoRole) are created alongside each repository to represent the permission levels available.

For repositories with active workflows, the collector records the applicable default workflow permissions and whether workflows may approve pull request reviews. These properties preserve the repository-level policy input later used to derive effective GITHUB_TOKEN permissions for GH_WorkflowJob nodes.
