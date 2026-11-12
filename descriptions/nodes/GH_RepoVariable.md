# GH_RepoVariable

## General Information

Represents a repository-level GitHub Actions variable. These are variables defined directly on a specific repository and are only accessible to workflows running in that repository. Unlike secrets, variable values are readable via the API.

## Diagram

```mermaid
graph LR
    n0["GH_Repository"]
    n1["GH_RepoVariable"]
    n2["GH_WorkflowJob"]
    n3["GH_WorkflowStep"]
    n0 -.->|GH_Contains| n1
    n0 -->|GH_HasVariable| n1
    n2 -.->|GH_UsesVariable| n1
    n3 -.->|GH_UsesVariable| n1
```

## References

- [Actions variables API](https://docs.github.com/en/rest/actions/variables)
