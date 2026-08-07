import pytest

from openhound_github.runner_ids import runner_group_node_id, runner_node_id


def test_runner_group_node_id_requires_scope_node_id() -> None:
    with pytest.raises(ValueError, match="scope_node_id is required"):
        runner_group_node_id(None, 1)


def test_runner_node_id_requires_scope_node_id() -> None:
    with pytest.raises(ValueError, match="scope_node_id is required"):
        runner_node_id(None, 1)


def test_runner_ids_preserve_scoped_identifier_formatting() -> None:
    assert runner_group_node_id("ORG_1", 2) == "ORG_1_runner_group_2"
    assert runner_node_id("ORG_1", 3) == "ORG_1_runner_3"
