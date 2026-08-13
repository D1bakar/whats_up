from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.whatsapp.exceptions import MessageParsingError
from app.whatsapp.meta.schemas import MetaWebhookPayload
from app.whatsapp.schemas import InboundEventKind, WhatsAppInboundEvent

logger = get_logger(__name__)

SUPPORTED_MESSAGE_TYPES = {"text"}


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError):
        return None


def _phone_number_id(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    metadata = value.get("metadata") or {}
    phone_number_id = metadata.get("phone_number_id")
    return str(phone_number_id) if phone_number_id else None


def parse_webhook_payload(payload: dict[str, Any]) -> list[WhatsAppInboundEvent]:
    """Convert a raw Meta webhook payload into internal inbound events."""

    events: list[WhatsAppInboundEvent] = []

    try:
        parsed = MetaWebhookPayload.model_validate(payload)
    except Exception as exc:
        logger.warning("webhook_payload_validation_failed", error=str(exc))
        raise MessageParsingError("Invalid webhook payload structure") from exc

    for entry in parsed.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue

            value = change.value.model_dump(by_alias=True)
            phone_number_id = _phone_number_id(value)

            for message in change.value.messages or []:
                message_type = message.type
                text = message.text.body if message.text else None
                kind = (
                    InboundEventKind.MESSAGE
                    if message_type in SUPPORTED_MESSAGE_TYPES
                    else InboundEventKind.UNSUPPORTED
                )

                events.append(
                    WhatsAppInboundEvent(
                        event_id=message.id,
                        message_id=message.id,
                        sender_id=message.from_,
                        message_type=message_type,
                        text=text,
                        timestamp=_parse_timestamp(message.timestamp),
                        phone_number_id=phone_number_id,
                        kind=kind,
                        metadata={
                            "entry_id": entry.id,
                            "change_field": change.field,
                            "contacts": [
                                c.model_dump(by_alias=True) for c in (change.value.contacts or [])
                            ],
                        },
                    ),
                )

            for status in change.value.statuses or []:
                events.append(
                    WhatsAppInboundEvent(
                        event_id=f"status:{status.id}:{status.status}",
                        message_id=status.id,
                        sender_id=status.recipient_id,
                        message_type="status",
                        text=None,
                        timestamp=_parse_timestamp(status.timestamp),
                        phone_number_id=phone_number_id,
                        kind=InboundEventKind.STATUS,
                        metadata={
                            "status": status.status,
                            "entry_id": entry.id,
                        },
                    ),
                )

            if change.value.errors:
                for index, error in enumerate(change.value.errors):
                    events.append(
                        WhatsAppInboundEvent(
                            event_id=f"error:{entry.id}:{index}",
                            message_id=None,
                            sender_id=None,
                            message_type="error",
                            text=str(error.get("message", "unknown error")),
                            timestamp=None,
                            phone_number_id=phone_number_id,
                            kind=InboundEventKind.UNKNOWN,
                            metadata={"error": error},
                        ),
                    )

    if not events and parsed.entry:
        logger.info("webhook_no_recognized_events", entry_count=len(parsed.entry))

    return events
