## Description

Represents a self-hosted runner owned at the GitHub Enterprise level. Enterprise runners are contained by GH_EnterpriseRunnerGroup nodes and exposed through GH_HasRunner. Repositories become eligible to use them through GH_CanUseRunner to an inherited GH_OrgRunnerGroup, then GH_InheritedFrom to the enterprise group, and finally GH_HasRunner to the runner.

The node captures runner metadata such as operating system, status, busy state, labels, and whether the runner is ephemeral when GitHub returns that property.
