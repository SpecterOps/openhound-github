## Description

Represents a self-hosted runner owned at the GitHub Enterprise level. Enterprise runners are contained by GH_EnterpriseRunnerGroup nodes and exposed through GH_HasRunner. Repositories become eligible for the organization-facing runner group through GH_IsEligibleFor. Repositories and branches that can dispatch workflows then reach the runner through GH_CanUseRunner to an inherited GH_OrgRunnerGroup, GH_InheritedFrom to the enterprise group, and finally GH_HasRunner to the runner.

The node captures runner metadata such as operating system, status, busy state, labels, and whether the runner is ephemeral when GitHub returns that property.
