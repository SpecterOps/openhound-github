from pydantic import BaseModel


class ActionPermission(BaseModel):
    enabled_repositories: str
    allowed_actions: str
    selected_actions_url: str
    sha_pinning_required: bool | None = None
