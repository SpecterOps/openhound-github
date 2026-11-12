# GH_OrgRunner

## General Information

Represents a self-hosted runner owned by a GitHub organization. Organization runners are contained by native GH_OrgRunnerGroup nodes and exposed through GH_HasRunner. Repositories become eligible for those groups through GH_IsEligibleFor, while repositories and branches that can dispatch workflows to them are linked through GH_CanUseRunner.

The node captures runner metadata such as operating system, status, busy state, labels, and whether the runner is ephemeral when GitHub returns that property.

GH_RunsOn edges from GH_WorkflowJob nodes identify statically resolvable jobs that GitHub could schedule on this runner under the current runner-group access policy. These edges do not indicate that the job has actually executed on the runner.

When the runner is not explicitly marked ephemeral, GH_CanInterceptJob edges identify workflow jobs whose future execution context may be exposed to an actor controlling the runner.

## Diagram

```mermaid
graph LR
    n0["GH_OrgRunnerGroup"]
    n1["GH_OrgRunner"]
    n0 -.->|GH_Contains| n1
    n0 -->|GH_HasRunner| n1
```

## References

- [Self-hosted runners API](https://docs.github.com/en/rest/actions/self-hosted-runners)
