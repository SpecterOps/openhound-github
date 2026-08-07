## General Information

The non-traversable GH_CanUseRunner edge represents that a repository can dispatch GitHub Actions jobs to a self-hosted runner. Repository-scoped runners receive this edge directly from their containing repository. Organization and enterprise runners receive composed GH_CanUseRunner edges derived from runner group containment and repository access policy.

For native organization runner groups, the composition path is `GH_Repository <- GH_GrantsAccessTo - GH_OrgRunnerGroup - GH_Contains -> GH_OrgRunner`. For inherited groups, the path continues through `GH_InheritedFrom` to the enterprise runner group and its contained GH_EnterpriseRunner nodes.
