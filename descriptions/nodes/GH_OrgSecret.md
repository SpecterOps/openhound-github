# GH_OrgSecret

## General Information

Represents an organization-level GitHub Actions secret. All and private/internal visibility uses shared organization-secret GH_Scope nodes; arbitrary selected visibility uses direct GH_HasSecret relationships from repositories.

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_OrgSecret"]
    n2["GH_Organization"]
    n3["GH_Repository"]
    n4["GH_Scope"]
    n5["GH_WorkflowJob"]
    n6["GH_WorkflowStep"]
    n2 -.->|GH_Contains| n1
    n3 -->|GH_HasSecret| n1
    n0 -->|GH_CanReadSecret| n4
    n4 -->|GH_ScopedTo| n1
    n5 -->|GH_CanAccessSecret| n1
    n5 -.->|GH_UsesSecret| n1
    n6 -.->|GH_UsesSecret| n1
```

## References

- [Actions secrets API](https://docs.github.com/en/rest/actions/secrets)
