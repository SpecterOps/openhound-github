## General Information

The non-traversable GH_HasWorkflow edge represents the relationship between a repository and its GitHub Actions workflows. This edge links each discovered workflow definition to its parent repository. Workflows are significant from a security perspective because they can execute arbitrary code with repository permissions, access secrets, and assume cloud identities. This structural edge enables analysts to enumerate which workflows exist in a given repository.
