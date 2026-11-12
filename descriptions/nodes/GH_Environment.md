# GH_Environment

## General Information

Represents a GitHub Actions deployment environment configured on a repository. Environments can have protection rules including required reviewers, wait timers, administrator bypass behavior, and deployment branch policies.

Repositories always contain their environments. When custom branch policies are configured, the environment also contains one or more GH_EnvironmentBranchPolicy nodes that describe which branches are allowed to deploy. Environment-scoped secrets and variables are modeled as child nodes of the environment and become available to workflow jobs that reference it.

GH_CanRequestOIDCTokenFor edges from GH_WorkflowJob nodes identify jobs with a static upper-bound capability to request a GitHub-signed OIDC token for this environment because their effective `GITHUB_TOKEN` permissions include `id-token:write`. Runtime permission recalculation, such as forked `pull_request` permission downgrades, may prevent a specific execution from requesting OIDC even when this edge exists.

## Diagram

```mermaid
graph LR
    n0["GH_Branch"]
    n1["GH_Environment"]
    n2["GH_EnvironmentBranchPolicy"]
    n3["GH_EnvironmentSecret"]
    n4["GH_EnvironmentVariable"]
    n5["GH_RepoRole"]
    n6["GH_Repository"]
    n7["GH_Team"]
    n8["GH_User"]
    n9["GH_WorkflowJob"]
    n0 -->|GH_CanDeployToEnvironment| n1
    n1 -.->|GH_Contains| n2
    n1 -.->|GH_Contains| n3
    n1 -->|GH_HasSecret| n3
    n1 -.->|GH_Contains| n4
    n1 -->|GH_HasVariable| n4
    n5 -->|GH_CanDeployToEnvironment| n1
    n5 -->|GH_CanEditEnvironment| n1
    n6 -->|GH_CanDeployToEnvironment| n1
    n6 -.->|GH_Contains| n1
    n7 -.->|GH_ApprovesDeploymentTo| n1
    n7 -->|GH_CanDeployToEnvironment| n1
    n8 -.->|GH_ApprovesDeploymentTo| n1
    n8 -->|GH_CanDeployToEnvironment| n1
    n9 -->|GH_CanRequestOIDCTokenFor| n1
    n9 -.->|GH_DeploysTo| n1
```

## References

- [Deployment environments API](https://docs.github.com/en/rest/deployments/environments)
