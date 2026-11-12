# GH_ManageRepoSecurityProducts

## General Information

The non-traversable GH_ManageRepoSecurityProducts edge represents a role's ability to manage repository-specific security product settings. This permission is available to Admin roles and custom roles that have been granted this specific permission. Unlike the broader GH_ManageSecurityProducts permission, this edge is scoped to repository-level security configuration such as repository-specific scanning settings and alert management. Disabling repository-level security products can create blind spots in vulnerability detection for the specific repository.

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_ManageRepoSecurityProducts| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
