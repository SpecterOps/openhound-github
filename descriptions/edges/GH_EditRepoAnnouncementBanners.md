# GH_EditRepoAnnouncementBanners

## General Information

The non-traversable GH_EditRepoAnnouncementBanners edge represents a role's ability to edit repository announcement banners displayed to visitors. This permission is available to Maintain and Admin roles and custom roles that have been granted this specific permission.

## Diagram

```mermaid
graph LR
    n0["GH_RepoRole"]
    n1["GH_Repository"]
    n0 -.->|GH_EditRepoAnnouncementBanners| n1
```

## References

- [Repository roles](https://docs.github.com/en/organizations/managing-access-to-your-organizations-repositories/repository-roles-for-an-organization)
