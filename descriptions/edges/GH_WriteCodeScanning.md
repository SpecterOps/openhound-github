# GH_WriteCodeScanning

## General Information

The non-traversable GH_WriteCodeScanning edge represents a role's ability to upload code scanning analysis results. This permission is available to Write, Maintain, and Admin roles and custom roles that have been granted this specific permission. An attacker could upload falsified SARIF results to suppress real alerts or inject misleading findings.

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_WriteCodeScanning| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
