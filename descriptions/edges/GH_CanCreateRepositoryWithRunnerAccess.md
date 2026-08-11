## General Information

The non-traversable GH_CanCreateRepositoryWithRunnerAccess edge is a computed edge indicating that a GH_OrgRole can create a repository whose visibility automatically places it in scope for a GH_OrgRunnerGroup.

This edge is emitted only for runner groups with `visibility=all` or `visibility=private`. Groups with `visibility=selected` require explicit repository assignment, so creating a repository does not automatically grant access to the group.

The computation follows repository-creation capability edges from the org role to the organization and then GH_Contains to the runner group. For `visibility=all`, public repository creation is included only when `allows_public_repositories=true`; otherwise the composition is limited to private and internal repository creation. Each edge includes a `query_composition` Cypher query showing the underlying graph evidence.

This edge represents latent repository eligibility subject to runner-group workflow policy. It is non-traversable because creating an eligible repository does not by itself prove that arbitrary jobs can dispatch to the group's runners.
