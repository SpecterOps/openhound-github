# GH_HasPersonalAccessTokenRequest

## General Information

The non-traversable GH_HasPersonalAccessTokenRequest edge represents the relationship between a user and their pending personal access token requests awaiting organizational approval. This edge links each pending token request back to the user who submitted it. Pending token requests are security-relevant because they represent access that may soon be granted, and reviewing them helps administrators understand what permissions users are requesting before approval. Organizations that require approval for fine-grained PATs will have these requests queued until an administrator acts on them.

## Diagram

```mermaid
graph LR
    n0["GH_User"]
    n1["GH_PersonalAccessTokenRequest"]
    n0 -.->|GH_HasPersonalAccessTokenRequest| n1
```

## References

- [Personal access token API](https://docs.github.com/en/rest/orgs/personal-access-tokens)
- [GitHub App installations API](https://docs.github.com/en/rest/apps/installations)
