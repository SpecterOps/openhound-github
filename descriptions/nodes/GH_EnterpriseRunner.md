## Description

Represents a self-hosted runner owned at the GitHub Enterprise level. Enterprise runners are contained by GH_EnterpriseRunnerGroup nodes and exposed through GH_HasRunner. Repositories become eligible for the organization-facing runner group through GH_IsEligibleFor. Repositories and branches that can dispatch workflows then reach the runner through GH_CanUseRunner to an inherited GH_OrgRunnerGroup, GH_InheritedFrom to the enterprise group, and finally GH_HasRunner to the runner.

The node captures runner metadata such as operating system, status, busy state, labels, and whether the runner is ephemeral when GitHub returns that property.

GH_RunsOn edges from GH_WorkflowJob nodes identify statically resolvable jobs that GitHub could schedule on this runner through the inherited enterprise runner-group topology. These edges do not indicate that the job has actually executed on the runner.

When the runner is not explicitly marked ephemeral, GH_CanInterceptJob edges identify workflow jobs whose future execution context may be exposed to an actor controlling the runner.
