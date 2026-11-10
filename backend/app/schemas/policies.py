from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints


class PolicyAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: StrictBool
    revision: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    language: Literal["en", "ar"]


class StaffPolicyProvision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal["in_person", "phone", "whatsapp", "email"]
    language: Literal["en", "ar"]
    revision: Annotated[str, StringConstraints(min_length=1, max_length=80)]
