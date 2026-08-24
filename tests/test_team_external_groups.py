import json
import logging
from unittest.mock import MagicMock

import requests

from openhound_github.kinds import edges as ek
from openhound_github.models import Team
from openhound_github.resources.organization import (
    OrgContext,
    SourceContext,
    team_external_groups,
)


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.url = "https://api.github.com/example"

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            response.url = self.url
            response._content = json.dumps(self._payload).encode()
            raise requests.HTTPError(response=response)


class _FakeClient:
    def __init__(
        self,
        pages: dict[str, list[list[dict]]],
        responses: dict[str, _FakeResponse] | None = None,
    ):
        self.pages = pages
        self.responses = responses or {}
        self.paginate_calls: list[tuple[str, dict]] = []
        self.get_calls: list[tuple[str, dict]] = []

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        return iter(self.pages.get(path, []))

    def get(self, path: str, **kwargs):
        self.get_calls.append((path, kwargs))
        return self.responses[path]


class _HTTPErrorPaginateClient(_FakeClient):
    def __init__(self, status_code: int):
        super().__init__({})
        self.status_code = status_code

    def paginate(self, path: str, **kwargs):
        self.paginate_calls.append((path, kwargs))
        response = requests.Response()
        response.status_code = self.status_code
        response.url = f"https://api.github.com{path}"
        raise requests.HTTPError(response=response)


def _ctx(client) -> SourceContext:
    return SourceContext(
        client=client,
        organizations=[OrgContext(client=client, org_name="acme")],
    )


def test_team_external_groups_collects_group_first_team_mappings() -> None:
    client = _FakeClient(
        {
            "/orgs/acme/external-groups": [
                [
                    {
                        "group_id": 100,
                        "group_name": "Engineering",
                        "updated_at": "2026-08-24T16:34:05Z",
                    },
                    {
                        "group_id": 200,
                        "group_name": "Security",
                        "updated_at": "2026-08-24T16:35:05Z",
                    },
                ]
            ],
            "/orgs/acme/teams": [
                [
                    {"id": 7, "slug": "engineering"},
                    {"id": 8, "slug": "platform"},
                    {"id": 9, "slug": "operations"},
                    {"id": 10, "slug": "ent:enterprise-team"},
                ]
            ],
        },
        {
            "/orgs/acme/external-group/100": _FakeResponse(
                {
                    "group_id": 100,
                    "group_name": "Engineering",
                    "updated_at": "2026-08-24T16:34:05Z",
                    "teams": [
                        {"team_id": 7, "team_name": "engineering"},
                        {"team_id": 8, "team_name": "platform"},
                    ],
                }
            ),
            "/orgs/acme/external-group/200": _FakeResponse(
                {
                    "group_id": 200,
                    "group_name": "Security",
                    "updated_at": "2026-08-24T16:35:05Z",
                    "teams": [],
                }
            ),
        },
    )

    rows = list(team_external_groups.__wrapped__(_ctx(client)))

    assert rows == [
        {
            "org_login": "acme",
            "team_database_id": 7,
            "external_group_id": 100,
            "external_group_name": "Engineering",
            "external_group_updated_at": "2026-08-24T16:34:05Z",
        },
        {
            "org_login": "acme",
            "team_database_id": 8,
            "external_group_id": 100,
            "external_group_name": "Engineering",
            "external_group_updated_at": "2026-08-24T16:34:05Z",
        },
    ]
    assert client.paginate_calls == [
        (
            "/orgs/acme/external-groups",
            {"params": {"per_page": 100}, "data_selector": "groups"},
        ),
        ("/orgs/acme/teams", {"params": {"per_page": 100}}),
    ]
    assert client.get_calls == [
        ("/orgs/acme/external-group/100", {}),
        ("/orgs/acme/external-group/200", {}),
    ]


def test_team_external_groups_uses_team_connections_when_teams_are_fewer() -> None:
    client = _FakeClient(
        {
            "/orgs/acme/external-groups": [
                [
                    {"group_id": 100, "group_name": "Engineering"},
                    {"group_id": 200, "group_name": "Security"},
                ]
            ],
            "/orgs/acme/teams": [
                [
                    {"id": 7, "slug": "engineering"},
                    {"id": 8, "slug": "ent:enterprise-team"},
                ]
            ],
        },
        {
            "/orgs/acme/teams/engineering/external-groups": _FakeResponse(
                {
                    "groups": [
                        {
                            "group_id": 100,
                            "group_name": "Engineering",
                            "updated_at": "2026-08-24T16:34:05Z",
                        }
                    ]
                }
            )
        },
    )

    rows = list(team_external_groups.__wrapped__(_ctx(client)))

    assert rows == [
        {
            "org_login": "acme",
            "team_database_id": 7,
            "external_group_id": 100,
            "external_group_name": "Engineering",
            "external_group_updated_at": "2026-08-24T16:34:05Z",
        }
    ]
    assert client.get_calls == [
        ("/orgs/acme/teams/engineering/external-groups", {}),
    ]


def test_team_external_groups_skips_missing_permission(caplog) -> None:
    client = _HTTPErrorPaginateClient(status_code=403)

    with caplog.at_level(
        logging.WARNING, logger="openhound_github.resources.organization"
    ):
        rows = list(team_external_groups.__wrapped__(_ctx(client)))

    assert rows == []
    assert any(
        "Skipping team_external_groups for organization 'acme': "
        "the configured credentials do not have Members organization permission at write level"
        in message
        for message in caplog.messages
    )


def test_team_external_groups_stops_after_detail_permission_failure(caplog) -> None:
    client = _FakeClient(
        {
            "/orgs/acme/external-groups": [
                [
                    {"group_id": 100, "group_name": "Engineering"},
                    {"group_id": 200, "group_name": "Security"},
                ]
            ],
            "/orgs/acme/teams": [
                [
                    {"id": 7, "slug": "engineering"},
                    {"id": 8, "slug": "platform"},
                    {"id": 9, "slug": "operations"},
                ]
            ],
        },
        {
            "/orgs/acme/external-group/100": _FakeResponse({}, status_code=403),
            "/orgs/acme/external-group/200": _FakeResponse(
                {
                    "group_id": 200,
                    "group_name": "Security",
                    "teams": [{"team_id": 8, "team_name": "platform"}],
                }
            ),
        },
    )

    with caplog.at_level(
        logging.WARNING, logger="openhound_github.resources.organization"
    ):
        rows = list(team_external_groups.__wrapped__(_ctx(client)))

    assert rows == []
    assert client.get_calls == [
        ("/orgs/acme/external-group/100", {}),
    ]
    assert any(
        "Skipping team_external_groups for organization 'acme': "
        "the configured credentials do not have Members organization permission at write level"
        in message
        for message in caplog.messages
    )


def test_team_external_groups_skips_teams_with_explicit_members() -> None:
    client = _FakeClient(
        {
            "/orgs/acme/external-groups": [
                [
                    {"group_id": 100, "group_name": "Engineering"},
                    {"group_id": 200, "group_name": "Security"},
                    {"group_id": 300, "group_name": "Operations"},
                ]
            ],
            "/orgs/acme/teams": [
                [
                    {"id": 7, "slug": "engineering"},
                    {"id": 8, "slug": "platform"},
                ]
            ],
        },
        {
            "/orgs/acme/teams/engineering/external-groups": _FakeResponse(
                {
                    "message": "This team cannot be externally managed since it has explicit members."
                },
                status_code=400,
            ),
            "/orgs/acme/teams/platform/external-groups": _FakeResponse(
                {
                    "groups": [
                        {
                            "group_id": 200,
                            "group_name": "Security",
                            "updated_at": "2026-08-24T16:35:05Z",
                        }
                    ]
                }
            ),
        },
    )

    rows = list(team_external_groups.__wrapped__(_ctx(client)))

    assert rows == [
        {
            "org_login": "acme",
            "team_database_id": 8,
            "external_group_id": 200,
            "external_group_name": "Security",
            "external_group_updated_at": "2026-08-24T16:35:05Z",
        }
    ]
    assert client.get_calls == [
        ("/orgs/acme/teams/engineering/external-groups", {}),
        ("/orgs/acme/teams/platform/external-groups", {}),
    ]


def test_team_node_includes_external_group_evidence() -> None:
    team = Team(
        id="T_1",
        databaseId=7,
        name="engineering",
        slug="engineering",
        members={"edges": [], "pageInfo": {"endCursor": None, "hasNextPage": False}},
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.org_id_for_login.return_value = "O_1"
    lookup.external_group_for_team.return_value = (100, "Engineering")
    team._lookup = lookup

    node = team.as_node

    assert node.properties.external_group_id == 100
    assert node.properties.external_group_name == "Engineering"
    lookup.external_group_for_team.assert_called_once_with("acme", 7)


def test_team_emits_scim_provisioned_edge_for_external_group_match() -> None:
    team = Team(
        id="T_1",
        databaseId=7,
        name="engineering",
        slug="engineering",
        members={"edges": [], "pageInfo": {"endCursor": None, "hasNextPage": False}},
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.external_group_for_team.return_value = (100, "Engineering")
    lookup.scim_group_id_for_team_external_group.return_value = "SCIM_1"
    lookup.bypass_pull_request_allowances.return_value = []
    lookup.bypass_push_restrictions.return_value = []
    team._lookup = lookup

    edges = list(team.edges)

    assert [edge.kind for edge in edges] == [ek.SCIM_PROVISIONED]
    assert edges[0].start.value == "SCIM_1"
    assert edges[0].end.value == "T_1"
    assert edges[0].properties.traversable is True
    lookup.scim_group_id_for_team_external_group.assert_called_once_with(
        "acme", "Engineering"
    )


def test_team_skips_scim_provisioned_edge_without_unique_scim_group_match() -> None:
    team = Team(
        id="T_1",
        databaseId=7,
        name="engineering",
        slug="engineering",
        members={"edges": [], "pageInfo": {"endCursor": None, "hasNextPage": False}},
        org_login="acme",
    )
    lookup = MagicMock()
    lookup.external_group_for_team.return_value = (100, "Engineering")
    lookup.scim_group_id_for_team_external_group.return_value = None
    lookup.bypass_pull_request_allowances.return_value = []
    lookup.bypass_push_restrictions.return_value = []
    team._lookup = lookup

    assert list(team.edges) == []
