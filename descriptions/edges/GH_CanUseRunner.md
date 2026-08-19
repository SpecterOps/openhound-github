## General Information

The non-traversable GH_CanUseRunner edge represents that a repository is eligible to use a self-hosted runner execution surface based on scope or runner-group repository access policy.

Repository-scoped runners receive this edge directly from their containing repository. Organization and inherited enterprise-backed access instead terminate at the organization-facing GH_OrgRunnerGroup. The graph then continues through GH_HasRunner for native organization runners, or through GH_InheritedFrom and GH_HasRunner for inherited enterprise runners.

For group-backed runners, this edge currently models repository visibility, selected repository access, and allows_public_repositories only. Workflow restrictions remain properties on the runner group and are not encoded into this edge yet.
