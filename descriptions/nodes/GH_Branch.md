# GH_Branch

## General Information

Represents a Git branch within a repository. Branch nodes capture basic branch information and whether the branch is protected. Protection rule details are stored in separate GH_BranchProtectionRule nodes, linked via GH_ProtectedBy edges.

## Diagram

```mermaid
graph LR
    n0["GH_Branch"]
    n1["GH_Environment"]
    n2["GH_EnvironmentBranchPolicy"]
    n3["GH_OrgRunnerGroup"]
    n4["GH_BranchProtectionRule"]
    n5["GH_RepoRole"]
    n6["GH_Repository"]
    n7["GH_Team"]
    n8["GH_User"]
    n0 -->|GH_CanDeployToEnvironment| n1
    n0 -.->|GH_MatchesEnvironmentPolicy| n2
    n0 -->|GH_CanUseRunner| n3
    n4 -.->|GH_ProtectedBy| n0
    n5 -.->|GH_CanEditProtection| n0
    n5 -->|GH_CanPwnRequest| n0
    n5 -.->|GH_CanWriteBranch| n0
    n6 -.->|GH_Contains| n0
    n7 -.->|GH_CanWriteBranch| n0
    n8 -.->|GH_CanWriteBranch| n0
```

## References

- [Branch protection API](https://docs.github.com/en/rest/branches/branch-protection)
