# GH_Runner

## General Information

Generic label applied to GitHub self-hosted runner nodes across enterprise, organization, and repository scope.

## Diagram

```mermaid
graph LR
    n0["GH_Runner"]
    n1["GH_WorkflowJob"]
    n0 -->|GH_CanInterceptJob| n1
    n1 -.->|GH_RunsOn| n0
```

## References

- [Self-hosted runners API](https://docs.github.com/en/rest/actions/self-hosted-runners)
