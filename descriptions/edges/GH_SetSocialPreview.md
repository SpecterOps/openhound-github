# GH_SetSocialPreview

## General Information

The non-traversable GH_SetSocialPreview edge represents a role's ability to set the repository social preview image shown in link previews. This permission is available to Maintain and Admin roles and custom roles that have been granted this specific permission.

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_SetSocialPreview| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
