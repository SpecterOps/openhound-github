from dlt.common import jsonpath
from dlt.sources.helpers.rest_client.paginators import (
    JSONResponseCursorPaginator,
)
from requests import Request


class GraphQLCursorPaginator(JSONResponseCursorPaginator):
    def __init__(
        self,
        page_info_path: str,
        cursor_variable: str = "after",
        cursor_field: str = "endCursor",
        has_next_field: str = "hasNextPage",
    ) -> None:

        super().__init__(
            cursor_path=f"{page_info_path}.{cursor_field}",  # Path to extract cursor
            cursor_param=None,
            cursor_body_path=None,  # We'll handle this manually in update_request
            stop_after_empty_page=False,
            has_more_path=f"{page_info_path}.{has_next_field}",  # Path to hasNextPage boolean
        )
        self.page_info_path = page_info_path
        self.cursor_variable = cursor_variable
        self.cursor_field = cursor_field
        self.has_next_field = has_next_field

    def update_state(self, response, data=None):
        response_json = response.json()
        page_info = jsonpath.find_values(self.page_info_path, response_json)

        if not page_info:
            self._next_reference = None
            self._has_next_page = False
            return

        page_info_obj = page_info[0]
        cursor = page_info_obj.get(self.cursor_field)
        has_next = page_info_obj.get(self.has_next_field)
        self._next_reference = cursor
        self._has_next_page = has_next

    def update_request(self, request: "Request") -> None:
        if not self._next_reference or not hasattr(request, "json"):
            return

        if isinstance(request.json, dict) and "variables" in request.json:
            request.json["variables"][self.cursor_variable] = self._next_reference
