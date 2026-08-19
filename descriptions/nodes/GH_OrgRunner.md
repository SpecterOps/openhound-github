## Description

Represents a self-hosted runner owned by a GitHub organization. Organization runners are contained by native GH_OrgRunnerGroup nodes and exposed through GH_HasRunner. Repositories become eligible for those groups through GH_IsEligibleFor, while repositories and branches that can dispatch workflows to them are linked through GH_CanUseRunner.

The node captures runner metadata such as operating system, status, busy state, labels, and whether the runner is ephemeral when GitHub returns that property.
