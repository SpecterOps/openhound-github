# General Information

The non-traversable `GH_OrgBypassSecretScanningClosureRequests` edge represents that a role can bypass secret scanning closure requests at the organization level. This edge is dynamically generated from custom organization role permissions discovered by the collector. This permission allows closing secret scanning alerts without going through the standard review and approval process, which is significant because an attacker could use it to suppress alerts about leaked credentials and prevent incident response teams from being notified.
