## General Information

The non-traversable GH_GrantsAccessTo edge represents that a GH_OrgRunnerGroup allows a repository to use the runners exposed by that group. For native groups, those runners are GH_OrgRunner nodes contained by the group. For inherited groups, those runners are GH_EnterpriseRunner nodes reached through GH_InheritedFrom.

This edge is used as part of the composition path for GH_CanUseRunner and is not traversable on its own because repository eligibility alone is not a privilege escalation path.
