## Description

Represents a GitHub App definition — the registered application entity. The app owner holds the private key that can generate installation access tokens for **every** `GH_AppInstallation` of this app. If the private key is compromised, all installations across all organizations are affected.

App definitions are retrieved via the public `GET /apps/{app_slug}` endpoint (no authentication required) after discovering unique app slugs from the organization's app installations.
