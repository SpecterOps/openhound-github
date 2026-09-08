# GH_InviteMember

## General Information

The non-traversable GH_InviteMember edge represents that a role has the ability to invite new members to the organization. This permission is typically restricted to Owners, as inviting members expands the organization's trust boundary by granting new users access to internal resources. An attacker with this permission could invite a controlled account to gain persistent access to the organization's repositories, teams, and secrets.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_OrgRole` | `GH_Organization` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n0 -.->|GH_InviteMember| n1
```
