"""Check that the collector's SAML output conforms to the producer contract."""

import json
from pathlib import Path

from openhound_saml_producer.testing.conformance import assert_conformant

from openhound_github.models.saml_producer import SAML

BASELINE_GRAPH = Path(__file__).parent / "test_data" / "saml_baseline" / "graph.json"


def test_baseline_graph_is_conformant() -> None:
    """The stored baseline is the collector's output for the #29 fixture input.

    `test_saml_baseline.py` compares the collector's output with this file
    exactly, so a conformant file means conformant collector output.
    """
    warnings = assert_conformant(
        {"graph": json.loads(BASELINE_GRAPH.read_text())}, producer=SAML
    )

    assert warnings == []
