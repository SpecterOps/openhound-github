# GH_DeleteDiscussionComment

## General Information

The non-traversable GH_DeleteDiscussionComment edge represents a role's ability to delete discussion comments authored by any user. This permission is available to Triage, Write, Maintain, and Admin roles and custom roles that have been granted this specific permission.

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_DeleteDiscussionComment| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
