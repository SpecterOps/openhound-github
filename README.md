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

### GitHub App JWT issuer

Enterprise GitHub App credentials accept either `client_id` or `app_id` as the
JWT issuer. When both are configured, `client_id` is preferred. At least one
identifier must be supplied together with `key_path` and `enterprise_name`.

### Enterprise SCIM and hybrid correlations

A token with enterprise SCIM access is used to collect both `/scim/v2/enterprises/{enterprise}/Users` and `/scim/v2/enterprises/{enterprise}/Groups`. The collector emits normalized `SCIM_Organization`, `SCIM_User`, and `SCIM_Group` nodes plus `SCIM_Contains`, `SCIM_MemberOf`, and `SCIM_Provisioned` relationships. Install the BloodHound SCIM extension alongside this extension to register the shared SCIM kinds.

`SOURCES__GITHUB__EMIT_LEGACY_SCIM_CORRELATIONS=true` temporarily reproduces GitHound-style Okta-to-SCIM correlation relationships. It defaults to false because a dedicated hybrid correlator should own IdP-to-SCIM matching; GitHub remains authoritative for GitHub's SCIM resources and target-system provisioning relationships.

Enterprise roles, including the built-in `members` role, are emitted through `GH_HasRole` and granular enterprise capability relationships. Only capability relationships with a confirmed privilege path are traversable; descriptive permissions such as `GH_WriteEnterpriseSso` remain non-traversable.

### Optional privileged collection

The collector runs successfully with the documented read-only permission set. Some higher-fidelity relationships require optional non-read-only permissions because GitHub exposes the supporting read APIs behind privileged permission names:

- Organization `Members: write` enables external group mapping collection for IdP-synced teams, which allows the converter to emit `SCIM_Provisioned` edges from `SCIM_Group` to `GH_Team`. This is useful when the organization uses team synchronization with an external identity provider; if no GitHub teams are linked to external groups, this permission does not add graph data.
- Classic PAT scope `manage_runners:enterprise` enables enterprise self-hosted runner group and runner collection. This is useful when the enterprise has enterprise-scoped runner groups or runners, especially runner groups shared into organizations; if all runners are organization- or repository-scoped, this scope does not add graph data.

If these optional permissions are not granted, OpenHound skips the affected resources and continues collecting the rest of the GitHub environment.

[![Python Version](https://img.shields.io/badge/Python-3.13-brightgreen.svg)](#about)

## Getting Started

Follow the OpenHound GitHub collector docs to get started:

- [GitHub collector overview](https://bloodhound.specterops.io/openhound/collectors/github/overview)
- [Configure the collector](https://bloodhound.specterops.io/openhound/collectors/github/collect-data)
- [Configure an organization GitHub App](https://bloodhound.specterops.io/openhound/collectors/github/configure-app)
- [Configure an enterprise GitHub App](https://bloodhound.specterops.io/openhound/collectors/github/configure-enterprise-app)
- [Configure a personal access token](https://bloodhound.specterops.io/openhound/collectors/github/configure-pat)
