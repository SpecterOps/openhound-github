from dlt.common import jsonpath
from dlt.sources.helpers.rest_client.paginators import (
    JSONResponseCursorPaginator,
)
from requests import Request


class GraphQLPaginationError(RuntimeError):
    pass


class GraphQLCursorPaginator(JSONResponseCursorPaginator):
    def __init__(
        self,
        page_info_path: str,
        cursor_variable: str = "after",
        cursor_field: str = "endCursor",
        has_next_field: str = "hasNextPage",
        allow_missing_page_info: bool = False,
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
        self.allow_missing_page_info = allow_missing_page_info

    def init_request(self, request: "Request") -> None:
        self._next_reference = None
        self._has_next_page = True

    def update_state(self, response, data=None):
        response_json = response.json()
        errors = response_json.get("errors")
        if errors:
            messages = []
            for error in errors:
                if isinstance(error, dict):
                    message = error.get("message", "unknown GraphQL error")
                    extensions = error.get("extensions") or {}
                    error_type = error.get("type") or extensions.get("type")
                    path = error.get("path")
                    details = message
                    if error_type:
                        details = f"{details} ({error_type})"
                    if path:
                        details = f"{details} at {path}"
                    messages.append(details)
                else:
                    messages.append(str(error))
            raise GraphQLPaginationError(
                f"GraphQL response contained errors while reading {self.page_info_path}: "
                + "; ".join(messages)
            )

        self._normalize_page_info(data)

        page_info = jsonpath.find_values(self.page_info_path, response_json)

        if not page_info:
            if not self.allow_missing_page_info:
                raise GraphQLPaginationError(
                    f"GraphQL pageInfo not found at {self.page_info_path}"
                )
            self._next_reference = None
            self._has_next_page = False
            return

        page_info_obj = page_info[0]
        cursor = page_info_obj.get(self.cursor_field)
        has_next = page_info_obj.get(self.has_next_field)

        if not isinstance(has_next, bool):
            raise GraphQLPaginationError(
                f"GraphQL {self.page_info_path}.{self.has_next_field} must be a bool"
            )
        if has_next and not cursor:
            raise GraphQLPaginationError(
                f"GraphQL {self.page_info_path}.{self.cursor_field} is required when "
                f"{self.has_next_field} is true"
            )

        self._next_reference = cursor
        self._has_next_page = has_next

    def _normalize_page_info(self, data):
        if isinstance(data, list):
            for item in data:
                self._normalize_page_info(item)
            return

        if not isinstance(data, dict):
            return

        page_info = data.get("pageInfo")
        if isinstance(page_info, dict):
            has_next = page_info.get(self.has_next_field)
            if has_next is False and self.cursor_field not in page_info:
                page_info[self.cursor_field] = None

        for value in data.values():
            self._normalize_page_info(value)

    def update_request(self, request: "Request") -> None:
        if not self._has_next_page:
            return

        if not self._next_reference:
            raise GraphQLPaginationError(
                f"GraphQL cursor is missing for variable {self.cursor_variable}"
            )
        if not isinstance(request.json, dict):
            raise GraphQLPaginationError("GraphQL request body must be a JSON object")
        variables = request.json.get("variables")
        if not isinstance(variables, dict):
            raise GraphQLPaginationError("GraphQL request body must contain variables")

        variables[self.cursor_variable] = self._next_reference
