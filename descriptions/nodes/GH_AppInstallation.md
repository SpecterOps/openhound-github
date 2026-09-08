## Description

Represents a GitHub App installed on an organization. App installations have specific permissions and can be scoped to all repositories or a selection of repositories. The permissions granted to the installation are stored as `scope:access` values such as `contents:write` in the `permissions` property.

Unlike fine-grained personal access tokens, GitHub does not expose separate organization and repository permission buckets for app installations, so this property remains a single flat permission list.

Each installation is linked to its parent GH_App via a GH_InstalledAs edge. For installations with `repository_selection` set to `all`, GH_CanAccess edges are created to every repository in the organization. For installations with `repository_selection` set to `selected`, repository-level edges cannot be enumerated with a PAT (requires app installation token authentication).
