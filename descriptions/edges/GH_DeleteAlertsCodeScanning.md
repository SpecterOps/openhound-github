## General Information

The non-traversable `GH_DeleteAlertsCodeScanning` edge represents a role's ability to delete code scanning alerts from the repository. This permission is available to Admin roles and custom roles that have been granted this specific permission. Deleting code scanning alerts can obscure security vulnerabilities that have been detected in the codebase, which is significant from an audit and compliance perspective. An attacker with this permission could suppress evidence of vulnerabilities they have introduced.
