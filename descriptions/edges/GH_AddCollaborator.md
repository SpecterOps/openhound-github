# GH_AddCollaborator

## General Information

The non-traversable GH_AddCollaborator edge represents that a role has the ability to add outside collaborators to organization repositories. This permission is typically restricted to Owners, as it grants repository access to external users who are not members of the organization. Outside collaborators bypass organizational membership controls, making this permission significant for security because it can be used to grant access to untrusted external identities without the visibility that full membership provides.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_OrgRole` | `GH_Organization` | `false` |

## Diagram

```mermaid
graph LR
    n0["GH_OrgRole"]
    n1["GH_Organization"]
    n0 -.->|GH_AddCollaborator| n1
```
