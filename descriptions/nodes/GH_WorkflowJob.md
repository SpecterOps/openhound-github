## Description

Represents a single job within a GitHub Actions workflow. Jobs are the top-level execution units of a workflow — they run on a runner, hold a set of steps, and can declare permissions, environments, and dependencies on other jobs.

When the job has a statically resolvable self-hosted `runs-on` selector, GH_RunsOn edges identify each GH_Runner that currently satisfies the declared label and runner-group constraints under the repository's runner access policy. These edges represent schedulability, not historical execution.
