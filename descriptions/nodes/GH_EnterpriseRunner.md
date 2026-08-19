## Description

Represents a self-hosted runner owned at the GitHub Enterprise level. Enterprise runners are contained by GH_EnterpriseRunnerGroup nodes and exposed through GH_HasRunner. Repositories become eligible to use them through an inherited GH_OrgRunnerGroup connected by GH_InheritedFrom.

The node captures runner metadata such as operating system, status, busy state, labels, and whether the runner is ephemeral when GitHub returns that property.
