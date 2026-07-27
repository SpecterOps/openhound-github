## General Information

The traversable GH_CanDeployToEnvironment edge represents the ability for a repository, branch, repository role, or self-approving reviewer to satisfy the modeled deployment constraints for a GitHub Environment.

This edge is computed from environment deployment branch policy, branch protection state, required reviewer behavior, and administrator bypass behavior. For environments without required reviewers, unrestricted environments emit repository and branch edges, protected-branch-only environments emit edges only for protected branches unless no branch protection rules exist, and custom branch policies emit edges only for matching branches.

When required reviewers are configured and self-review is allowed, the configured GH_User or GH_Team reviewer receives GH_CanDeployToEnvironment because that reviewer can satisfy the approval gate themselves. When prevent_self_review is enabled, no direct deploy edge is emitted for the reviewer because the required split-principal flow is not currently modeled. GH_ApprovesDeploymentTo remains non-traversable reviewer context in both cases.
