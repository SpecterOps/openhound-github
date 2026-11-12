# GH_DeployKey

## General Information

A repository-scoped SSH deploy key that grants read-only or read-write access to repository contents.

## Diagram

```mermaid
graph LR
    n0["GH_DeployKey"]
    n1["GH_Repository"]
    n2["GH_User"]
    n0 -.->|GH_CanAccess| n1
    n1 -.->|GH_Contains| n0
    n2 -.->|GH_AddedDeployKey| n0
```

## References

- [Deploy keys API](https://docs.github.com/en/rest/deploy-keys/deploy-keys)
