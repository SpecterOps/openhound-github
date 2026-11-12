# GH_WriteOrganizationActionsSettings

## General Information

The non-traversable GH_WriteOrganizationActionsSettings edge represents that a role can modify organization-level GitHub Actions settings. This edge is dynamically generated from custom organization role permissions discovered by the collector. These settings control which actions are allowed to run within the organization and the default permissions granted to the `GITHUB_TOKEN` in workflows. An attacker with this permission could weaken restrictions to allow untrusted third-party actions or elevate default token permissions to enable write access across repositories.

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n0 -.->|GH_WriteOrganizationActionsSettings| n1
```

## References

- [Organization roles](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/roles-in-an-organization)
- [Custom organization role API](https://docs.github.com/en/enterprise-cloud@latest/rest/orgs/organization-roles)
