## Description

Represents a single job within a GitHub Actions workflow. Jobs are the top-level execution units of a workflow — they run on a runner, hold a set of steps, and can declare permissions, environments, and dependencies on other jobs.

When the job has a statically resolvable self-hosted `runs-on` selector, GH_RunsOn edges identify each GH_Runner that currently satisfies the declared label and runner-group constraints under the repository's runner access policy. These edges represent schedulability, not historical execution.

When present, `job_permissions` captures the job-level `permissions` declaration from the workflow YAML. `effective_github_token_permissions` captures the calculated static `GITHUB_TOKEN` permissions after applying the repository default, workflow-level declaration, and job-level declaration.

GH_CanAccessSecret edges identify secrets statically referenced by the job's modeled steps or job-level `env` block that the job execution context can access. GH_CanInterceptJob edges from GH_Runner nodes not explicitly marked ephemeral identify jobs whose future execution context may be exposed if that runner is controlled. When a job targets an environment and its effective permissions include `id-token:write`, GH_CanRequestOIDCTokenFor identifies the environment OIDC context that code executing in the job can request.
