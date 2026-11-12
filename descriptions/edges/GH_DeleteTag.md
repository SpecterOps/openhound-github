# GH_DeleteTag

## General Information

The non-traversable GH_DeleteTag edge represents a role's ability to delete tags and releases. This permission is available to Admin roles and custom roles that have been granted this specific permission. Deleting tags can break downstream dependency references and remove published artifacts.

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_DeleteTag| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
