"""Bounded browser diagnostic contracts."""

from pydantic import BaseModel, ConfigDict, Field


class ClientErrorRequest(BaseModel):
    """Accept an error message and stack without browser storage or request bodies."""

    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    stack: str = Field(default="", max_length=16000)


class ClientErrorResponse(BaseModel):
    """Acknowledge a diagnostic accepted into the UI service log."""

    status: str = "accepted"
