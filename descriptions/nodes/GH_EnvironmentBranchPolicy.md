# GH_EnvironmentBranchPolicy

## General Information

Represents a deployment branch policy attached to a GitHub Environment. These policies define which branches or branch patterns are allowed to deploy to the environment, such as `main`, `release/*`, or `release/**/*`.

Environment branch policies are modeled as their own nodes so analysts can distinguish between the environment itself and the matching rules that govern deployment eligibility.

## Diagram

```mermaid
graph LR
    n0["GH_Branch"]
    n1["GH_EnvironmentBranchPolicy"]
    n2["GH_Environment"]
    n0 -.->|GH_MatchesEnvironmentPolicy| n1
    n2 -.->|GH_Contains| n1
```

## References

- [Deployment environments API](https://docs.github.com/en/rest/deployments/environments)
