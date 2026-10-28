# GH_Owns

## General Information

The traversable GH_Owns edge represents that a GitHub account owns an application or repository. For GitHub Apps, ownership identifies the account whose authorized administrators can manage the App registration and credentials. For repositories, ownership links the repository to its organization. These control relationships are traversable for attack-path analysis.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_Enterprise` | `GH_App` | `true` |
| `GH_Organization` | `GH_App` | `true` |
| `GH_Organization` | `GH_Repository` | `true` |
| `GH_User` | `GH_App` | `true` |

## Diagram

```mermaid
graph LR
    n0["GH_Enterprise"]
    n1["GH_App"]
    n2["GH_Organization"]
    n3["GH_Repository"]
    n4["GH_User"]
    n0 -->|GH_Owns| n1
    n2 -->|GH_Owns| n1
    n2 -->|GH_Owns| n3
    n4 -->|GH_Owns| n1
```
