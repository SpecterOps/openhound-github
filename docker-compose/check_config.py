"""Validate local configuration without contacting GitHub or BHE."""

import importlib.metadata
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import dlt
from dlt.common.configuration import resolve_configuration
from joserfc.jwk import RSAKey
from openhound_github.source import GithubEnterpriseAppCredentials


def required(name):
    value = dlt.secrets.get(name)
    if value is None or not str(value).strip() or "REPLACE_WITH" in str(value):
        raise ValueError(f"Set {name} in .dlt/secrets.toml")
    return str(value)


url = required("destination.bloodhoundenterprise.url")
if urlparse(url).scheme != "https" or not urlparse(url).hostname:
    raise ValueError("Set a valid HTTPS BHE tenant URL")
required("destination.bloodhoundenterprise.token_id")
required("destination.bloodhoundenterprise.token_key")
required("sources.source.github.credentials.enterprise_name")

credentials = resolve_configuration(
    GithubEnterpriseAppCredentials(),
    sections=("sources", "source", "github", "credentials"),
)
issuer = credentials.client_id or credentials.app_id
if not issuer or "REPLACE_WITH" in str(issuer):
    raise ValueError("Set the GitHub App client_id or app_id")
key_path = Path(credentials.key_path)
key = RSAKey.import_key(key_path.read_bytes())
if not key.is_private:
    raise ValueError("The GitHub App PEM must contain a private key")

for directory in (
    Path.cwd(),
    Path(os.environ["DLT_DATA_DIR"]),
    Path(os.environ["PIPELINES_DIR"]),
    Path(os.environ["RUNTIME__LOG_PATH"]),
    Path("/tmp/openhound"),
):
    with tempfile.TemporaryFile(mode="w+", dir=directory) as probe:
        probe.write("ok")

print("PASS: BHE and enterprise-app configuration resolves; RSA private key is readable.")
print("PASS: collection, state, lookup, and log directories are writable.")
print("GitHub collector version:", importlib.metadata.version("openhound-github"))
print("Preflight does not verify credentials against GitHub or BHE.")
