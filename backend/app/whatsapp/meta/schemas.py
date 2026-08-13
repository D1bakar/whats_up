from typing import Any

from pydantic import BaseModel, Field


class MetaTextBody(BaseModel):
    body: str


class MetaMessage(BaseModel):
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str
    text: MetaTextBody | None = None

    model_config = {"populate_by_name": True}


class MetaContact(BaseModel):
    wa_id: str
    profile: dict[str, Any] | None = None


class MetaStatus(BaseModel):
    id: str
    status: str
    timestamp: str
    recipient_id: str


class MetaValue(BaseModel):
    messaging_product: str | None = None
    metadata: dict[str, Any] | None = None
    contacts: list[MetaContact] | None = None
    messages: list[MetaMessage] | None = None
    statuses: list[MetaStatus] | None = None
    errors: list[dict[str, Any]] | None = None


class MetaChange(BaseModel):
    field: str
    value: MetaValue


class MetaEntry(BaseModel):
    id: str
    changes: list[MetaChange] = Field(default_factory=list)


class MetaWebhookPayload(BaseModel):
    object: str | None = None
    entry: list[MetaEntry] = Field(default_factory=list)
