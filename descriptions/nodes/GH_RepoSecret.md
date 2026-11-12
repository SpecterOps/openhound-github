# GH_RepoSecret

## General Information

Represents a repository-level GitHub Actions secret. These are secrets defined directly on a specific repository and are only accessible to workflows running in that repository.

## Diagram

```mermaid
graph LR
    n0["GH_Repository"]
    n1["GH_RepoSecret"]
    n2["GH_WorkflowJob"]
    n3["GH_WorkflowStep"]
    n0 -.->|GH_Contains| n1
    n0 -->|GH_HasSecret| n1
    n2 -->|GH_CanAccessSecret| n1
    n2 -.->|GH_UsesSecret| n1
    n3 -.->|GH_UsesSecret| n1
```

## References

- [Actions secrets API](https://docs.github.com/en/rest/actions/secrets)
