from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class Name(BaseModel):
    given_name: str | None = Field(default=None, alias="givenName")
    family_name: str | None = Field(default=None, alias="familyName")
    formatted: str | None = None


class ScimResource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    external_id: str = Field(alias="externalId")
    user_name: str = Field(alias="userName")
    display_name: str | None = Field(alias="displayName", default=None)
    name: Name
    emails: Optional[list[dict]] = Field(default_factory=list)
    groups: Optional[list[dict]] = Field(default_factory=list)
    roles: Optional[list[dict]] = Field(default_factory=list)
    active: bool
