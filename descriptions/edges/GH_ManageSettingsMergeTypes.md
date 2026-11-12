# GH_ManageSettingsMergeTypes

## General Information

The non-traversable GH_ManageSettingsMergeTypes edge represents a role's ability to configure allowed merge types (merge commit, squash, rebase) on the repository. This permission is available to Maintain and Admin roles and custom roles that have been granted this specific permission.

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_ManageSettingsMergeTypes| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
