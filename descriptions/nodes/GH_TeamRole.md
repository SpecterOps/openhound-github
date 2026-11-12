# GH_TeamRole

## General Information

Represents a role within a GitHub team. Each team has two built-in roles: Member and Maintainer. Maintainers can add and remove team members. Team roles connect users to teams and transitively to any repository roles assigned to the team.

## Diagram

```mermaid
graph LR
    n0["GH_TeamRole"]
    n1["GH_EnterpriseTeam"]
    n2["GH_Team"]
    n3["GH_User"]
    n0 -->|GH_MemberOf| n1
    n0 -.->|GH_AddMember| n2
    n0 -->|GH_MemberOf| n2
    n3 -->|GH_HasRole| n0
```

## References

- [Team membership API](https://docs.github.com/en/rest/teams/members)
