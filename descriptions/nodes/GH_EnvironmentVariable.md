# GH_EnvironmentVariable

## General Information

Represents an environment-level GitHub Actions variable. These variables are scoped to a specific deployment environment and are only available to workflow jobs that reference that environment. Unlike secrets, variable values are readable via the API.

The containing environment is linked to the variable with GH_Contains and GH_HasVariable edges. Workflow steps that reference the variable by name receive GH_UsesVariable edges when their job targets the same environment.

## Diagram

```mermaid
graph LR
    n0["GH_Environment"]
    n1["GH_EnvironmentVariable"]
    n2["GH_WorkflowJob"]
    n3["GH_WorkflowStep"]
    n0 -.->|GH_Contains| n1
    n0 -->|GH_HasVariable| n1
    n2 -.->|GH_UsesVariable| n1
    n3 -.->|GH_UsesVariable| n1
```

## References

- [Actions variables API](https://docs.github.com/en/rest/actions/variables)
