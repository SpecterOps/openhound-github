# GH_OrgVariable

## General Information

Represents an organization-level GitHub Actions variable. All and private/internal visibility uses shared organization-variable GH_Scope nodes; arbitrary selected visibility uses direct GH_HasVariable relationships from repositories. Unlike secrets, variable values are readable via the API.

## Diagram

```mermaid
graph LR
    n0["GH_Organization"]
    n1["GH_OrgVariable"]
    n2["GH_Repository"]
    n3["GH_Scope"]
    n4["GH_WorkflowJob"]
    n5["GH_WorkflowStep"]
    n0 -.->|GH_Contains| n1
    n2 -->|GH_HasVariable| n1
    n3 -->|GH_ScopedTo| n1
    n4 -.->|GH_UsesVariable| n1
    n5 -.->|GH_UsesVariable| n1
```

## References

- [Actions variables API](https://docs.github.com/en/rest/actions/variables)
