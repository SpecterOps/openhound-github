# GH_EnterpriseTeam

## General Information

A team managed at the GitHub Enterprise level and assignable across organizations.

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_EnterpriseTeam"]
    n2["GH_EnterpriseRole"]
    n3["GH_Organization"]
    n4["GH_Team"]
    n5["GH_TeamRole"]
    n0 -.->|GH_Contains| n1
    n1 -->|GH_HasRole| n2
    n1 -.->|GH_AssignedTo| n3
    n1 -->|GH_MemberOf| n4
    n5 -->|GH_MemberOf| n1
```

## References

- [Enterprise roles](https://docs.github.com/en/enterprise-cloud@latest/rest/enterprise-admin/enterprise-roles)
