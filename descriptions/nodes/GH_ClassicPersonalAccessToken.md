# GH_ClassicPersonalAccessToken

## General Information

A classic personal access token found in the enterprise credential inventory.

## Diagram

```mermaid
graph LR
    n0["GH_ClassicPersonalAccessToken"]
    n1["GH_Organization"]
    n2["GH_Enterprise"]
    n3["GH_User"]
    n0 -.->|GH_AuthorizedForOrganization| n1
    n2 -.->|GH_Contains| n0
    n3 -.->|GH_HasPersonalAccessToken| n0
```

## References

- [Personal access token API](https://docs.github.com/en/rest/orgs/personal-access-tokens)
