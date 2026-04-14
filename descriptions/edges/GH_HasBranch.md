## General Information

The non-traversable `GH_HasBranch` edge represents the relationship between a repository and its branches. This edge links each collected branch to its parent repository. It is a structural edge that provides the foundation for understanding branch-level protections and access controls. While not traversable itself, it connects repositories to branches where traversable edges like `GH_CanWriteBranch` and `GH_CanEditProtection` model the effective access.
