## Description

Represents a GitHub Actions deployment environment configured on a repository. Environments can have protection rules including required reviewers, wait timers, administrator bypass behavior, and deployment branch policies.

Repositories always contain their environments. When custom branch policies are configured, the environment also contains one or more GH_EnvironmentBranchPolicy nodes that describe which branches are allowed to deploy. Environment-scoped secrets and variables are modeled as child nodes of the environment and become available to workflow jobs that reference it.
