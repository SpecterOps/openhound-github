from pydantic import BaseModel


class ActionPermission(BaseModel):
    enabled_repositories: str
    allowed_actions: str
    selected_actions_url: str | None = None
    sha_pinning_required: bool | None = None

    # Additional
    org_login: str
