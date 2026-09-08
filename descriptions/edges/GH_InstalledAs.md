# GH_InstalledAs

## General Information

The traversable GH_InstalledAs edge links a GitHub App to its installation within the organization. This edge is traversable because it connects the app definition to its active installation, which determines the specific set of repositories and permissions the app has been granted. Understanding the relationship between an app and its installation is essential for tracing how app-level permissions translate into repository access.

## Edge Schema

| Source | Destination | Traversable |
| --- | --- | --- |
| `GH_App` | `GH_AppInstallation` | `true` |

## Diagram

```mermaid
graph LR
    n0["GH_App"]
    n1["GH_AppInstallation"]
    n0 -->|GH_InstalledAs| n1
```
