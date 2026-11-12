# GH_ReadCodeScanning

## General Information

The non-traversable GH_ReadCodeScanning edge represents a role's ability to read code scanning analysis results and alerts. This permission is available to Write, Maintain, and Admin roles and custom roles that have been granted this specific permission. Code scanning alerts may reveal exploitable vulnerabilities in the codebase.

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_ReadCodeScanning| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
