# GH_Team

## General Information

Represents a GitHub team within the organization. Teams can have parent-child relationships, contain members with different roles (Member, Maintainer), and be assigned to repository roles.

## Diagram

```mermaid
graph LR
    n0["GH_EnterpriseTeam"]
    n1["GH_Team"]
    n2["GH_Branch"]
    n3["GH_Environment"]
    n4["GH_OrgRole"]
    n5["GH_RepoRole"]
    n6["GH_TeamRole"]
    n0 -->|GH_MemberOf| n1
    n1 -.->|GH_CanWriteBranch| n2
    n1 -.->|GH_ApprovesDeploymentTo| n3
    n1 -->|GH_CanDeployToEnvironment| n3
    n1 -->|GH_HasRole| n4
    n1 -->|GH_HasRole| n5
    n1 -.->|GH_MemberOf| n1
    n6 -.->|GH_AddMember| n1
    n6 -->|GH_MemberOf| n1
```

## References

- [Team membership API](https://docs.github.com/en/rest/teams/members)
