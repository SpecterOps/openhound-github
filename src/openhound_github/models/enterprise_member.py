from datetime import datetime
from typing import ClassVar

from dlt.common.libs.pydantic import DltConfig
from pydantic import BaseModel, Field


class EmbeddedUser(BaseModel):
    id: str
    database_id: int = Field(alias="databaseId")
    login: str
    name: str | None = None
    email: str
    company: str | None = None


class BaseUser(BaseModel):
    dlt_config: ClassVar[DltConfig] = {"return_validated_models": True}

    typename: str = Field(alias="__typename")
    id: str
    login: str
    name: str | None = None
    url: str | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    user: EmbeddedUser | None = None


def flatten_enterprise_member(
    member: dict, enterprise_node_id: str, enterprise_slug: str
) -> tuple[dict | None, dict | None]:
    if member.get("__typename") == "EnterpriseUserAccount":
        managed_user = {
            **member,
            "enterprise_node_id": enterprise_node_id,
            "enterprise_slug": enterprise_slug,
        }
        user = member.get("user")
        if user and user.get("id"):
            return (
                {
                    **user,
                    "enterprise_node_id": enterprise_node_id,
                    "enterprise_slug": enterprise_slug,
                    "has_direct_enterprise_membership": False,
                },
                managed_user,
            )
        return None, managed_user

    if member.get("id"):
        return (
            {
                **member,
                "enterprise_node_id": enterprise_node_id,
                "enterprise_slug": enterprise_slug,
                "has_direct_enterprise_membership": True,
            },
            None,
        )

    return None, None
