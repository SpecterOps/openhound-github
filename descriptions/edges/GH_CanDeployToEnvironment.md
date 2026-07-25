## General Information

The traversable GH_CanDeployToEnvironment edge represents the ability for a repository, branch, or repository role to satisfy the modeled deployment branch policy or administrator bypass condition for a GitHub Environment.

This edge is computed from environment deployment branch policy, branch protection state, and administrator bypass behavior. For unrestricted environments, the repository and all contained branches may receive this edge. For protected-branch-only environments, only protected branches receive it unless the repository has no branch protection rules at all, in which case all branches can deploy. For custom branch policies, only branches matching a GH_EnvironmentBranchPolicy receive the edge.

Required reviewers and wait timers are represented as environment metadata and GH_ApprovesDeploymentTo context rather than as additional GH_CanDeployToEnvironment edges. A branch edge therefore means the branch is eligible to target the environment, not that every runtime approval or timing gate has already been satisfied.
