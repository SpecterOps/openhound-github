# GH_EnvironmentSecret

## General Information

Represents an environment-level GitHub Actions secret. These secrets are scoped to a specific deployment environment and are only available to workflow jobs that reference that environment.

The containing environment is linked to the secret with GH_Contains and GH_HasSecret edges. Workflow steps that reference the secret by name receive GH_UsesSecret edges when their job targets the same environment.

## Diagram

```mermaid
graph LR
    n0["GH_Environment"]
    n1["GH_EnvironmentSecret"]
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
