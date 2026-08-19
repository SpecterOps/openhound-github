## General Information

The non-traversable GH_ApprovesDeploymentTo edge represents that a user or team is configured as a required reviewer for a GitHub Environment.

This edge is emitted from GH_User or GH_Team nodes to GH_Environment nodes when the environment includes a required reviewer protection rule. Required reviewers act as an approval gate before jobs referencing the environment can continue.

The edge is non-traversable because it records reviewer configuration rather than direct deployment access. When self-review is allowed, the same reviewer may also receive a traversable GH_CanDeployToEnvironment edge only if they can also supply deployable code through GH_CanCreateBranch or GH_CanWriteBranch under the environment's branch policy. When prevent_self_review is enabled, GH_ApprovesDeploymentTo remains context only because the split-principal approval flow is not currently modeled.
