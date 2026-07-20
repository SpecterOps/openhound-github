<p align="center">
  <a href="https://specterops.io" target="_blank">
    <img alt="A project powered by SpecterOps - Creators of BloodHound" src=".github/GitHub-Header.png" width="100%" style="max-width: 100%;">
  </a>
</p>

<h4 align="center">
  Github collector for OpenHound
</h4>

<!-- Standard shields, please do not remove -->
<p align="center">
  <a href="https://slack.specterops.io"><img src="https://custom-icon-badges.demolab.com/badge/Slack-BloodHound%20Gang-4A154B?logo=slack&logoColor=fff" alt="Slack"/></a>
  <a href="https://reddit.com/r/SpecterOpsCommunity"><img src="https://img.shields.io/badge/Reddit-r/SpecterOpsCommunity-FF4500?logo=reddit&logoColor=white" alt="SpecterOps on Reddit"/></a>
  <a href="https://github.com/specterops"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fspecterops%2F.github%2Fmain%2Fconfig%2Fshield.json&style=flat" alt="Sponsored by SpecterOps"/></a>
</p>


<p align="center">
  <a href="https://x.com/SpecterOps"><img src="https://img.shields.io/twitter/follow/SpecterOps?style=social" alt="@SpecterOps on Twitter"/></a>
  <a href="https://www.linkedin.com/company/specterops/"><img src="https://custom-icon-badges.demolab.com/badge/LinkedIn-0A66C2?logo=linkedin-white&logoColor=fff" alt="Connect on LinkedIn"/></a>
  <a href="https://infosec.exchange/@specterops"><img src="https://img.shields.io/mastodon/follow/109314317500800201?domain=https%3A%2F%2Finfosec.exchange&style=social" alt="Connect on Mastodon"/></a>
</p>

---

## About

OpenHound is a standardized framework for building and running OpenGraph collectors and converters. It is built in
Python and powered by the [Data Load Tool (DLT)](https://dlthub.com/docs/intro) library, giving you a consistent
workflow to collect, process, and convert data from any source into BloodHound-compatible graphs.

The openhound-github extension collects resources from Github organizations and transforms these into useable nodes and
edges for
BloodHound.

### Enterprise SCIM and hybrid correlations

Enterprise App collection covers the enterprise itself and every organization installed for the configured GitHub App;
token-based enterprise collection covers only enterprise resources. When
`SOURCES__GITHUB__COLLECT_ENTERPRISE_SCIM=true`, a token with enterprise SCIM access is used to collect both
`/scim/v2/enterprises/{enterprise}/Users` and `/scim/v2/enterprises/{enterprise}/Groups`. The collector emits normalized
`SCIM_Organization`, `SCIM_User`, and `SCIM_Group` nodes plus `SCIM_Contains`, `SCIM_MemberOf`, and
`SCIM_Provisioned` relationships. Install the
[BloodHound SCIM extension](https://github.com/SpecterOps/bloodhound-scim-extension) with this extension to register the
shared SCIM kinds.

`SOURCES__GITHUB__EMIT_LEGACY_SCIM_CORRELATIONS=true` temporarily reproduces GitHound's Okta-to-SCIM correlation
relationships. It defaults to false because a future hybrid `openhound-scim` correlator should own IdP-to-SCIM matching;
GitHub remains authoritative for GitHub's SCIM resources and target-system provisioning relationships.

### GitHub deployment scope and SAML IDs

The configured GitHub API `host` identifies the deployment. `https://api.github.com` preserves the established
`github:saml:*` IDs and `https://github.com` routes. GitHub Enterprise Server output includes the normalized deployment
authority in synthetic SAML node IDs and derives ACS/entity routes from that deployment's web origin, so identical
enterprise or organization slugs on different servers cannot merge.

This is backward compatible for GitHub.com. Pre-fix GHES SAML output used cloud-shaped synthetic IDs and routes; before
ingesting replacement GHES output, remove those old normalized SAML nodes/edges or reset the disposable validation graph.
The collector does not delete or reconcile prior nodes automatically. The deployment-scoping behavior is covered with
mocked GHES hosts because no GHES platform is required for KNG validation.

When `SOURCES__GITHUB__AZUREHOUND_PATH` points to AzureHound CE JSON, the collector emits deduplicated
`GH_CanAssumeIdentity` relationships for GitHub Actions OIDC subjects. AzureHound remains authoritative for
`AZFederatedIdentityCredential` nodes, and a future hybrid correlator should eventually own this cross-source matching.

Enterprise roles, including the built-in members role, are converted to `GH_HasRole` and granular enterprise capability
relationships rather than a single coarse permission edge.

[![Python Version](https://img.shields.io/badge/Python-3.13-brightgreen.svg)](#about)

## Getting Started

Follow the OpenHound docs to get started:

- [OpenHound Documentation](https://bloodhound.specterops.io/openhound/overview)
