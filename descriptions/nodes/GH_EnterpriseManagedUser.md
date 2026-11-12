# GH_EnterpriseManagedUser

## General Information

A GitHub Enterprise managed user account linked to an enterprise identity provider.

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_EnterpriseManagedUser"]
    n2["GH_User"]
    n0 -.->|GH_HasMember| n1
    n1 -.->|GH_MapsToUser| n2
```

## References

- [Enterprise SCIM API](https://docs.github.com/en/enterprise-cloud@latest/rest/enterprise-admin/scim)
