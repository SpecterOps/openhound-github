# GH_WorkflowStep

## General Information

Represents a single step within a GitHub Actions job. A step is either a `uses:` action reference or a `run:` shell command. Steps are the leaf nodes of the workflow execution tree and are the primary location where secrets and variables are consumed.

## Diagram

```mermaid
graph LR
    n0["GH_WorkflowJob"]
    n1["GH_WorkflowStep"]
    n2["GH_EnvironmentSecret"]
    n3["GH_EnvironmentVariable"]
    n4["GH_OrgSecret"]
    n5["GH_OrgVariable"]
    n6["GH_RepoSecret"]
    n7["GH_RepoVariable"]
    n0 -.->|GH_Contains| n1
    n1 -.->|GH_UsesSecret| n2
    n1 -.->|GH_UsesVariable| n3
    n1 -.->|GH_UsesSecret| n4
    n1 -.->|GH_UsesVariable| n5
    n1 -.->|GH_UsesSecret| n6
    n1 -.->|GH_UsesVariable| n7
```

## References

- [Secure use of GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use)
