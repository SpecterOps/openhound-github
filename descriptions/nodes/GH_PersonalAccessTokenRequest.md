# GH_PersonalAccessTokenRequest

## General Information

Represents a pending request from an organization member to access organization resources with a fine-grained personal access token. PAT requests are linked to their owning user and the organization. An all-repository request also has a non-traversable GH_RequestsAccessTo edge to the organization's repository/all GH_Scope.

The requested permissions are stored separately as `organization_permissions` and `repository_permissions`. Each property is a list of `scope:access` values such as `members:read` or `contents:write`, matching the permission format used on GH_WorkflowJob nodes.

## Diagram

```mermaid
graph LR
    n0["GH_Organization"]
    n1["GH_PersonalAccessTokenRequest"]
    n2["GH_Scope"]
    n3["GH_User"]
    n0 -.->|GH_Contains| n1
    n1 -.->|GH_RequestsAccessTo| n2
    n3 -.->|GH_HasPersonalAccessTokenRequest| n1
```

## References

- [Personal access token API](https://docs.github.com/en/rest/orgs/personal-access-tokens)
