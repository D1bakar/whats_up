from app.bot.exceptions import InvalidInboundMessageError
from app.bot.schemas import InternalInboundMessage
from app.whatsapp.schemas import WhatsAppInboundEvent


def to_internal_message(event: WhatsAppInboundEvent) -> InternalInboundMessage:
    """Convert a provider-normalized event into a bot-layer inbound message."""

    if not event.message_id:
        raise InvalidInboundMessageError("Missing message_id")
    if not event.sender_id:
        raise InvalidInboundMessageError("Missing sender identity")
    if not event.phone_number_id:
        raise InvalidInboundMessageError("Missing phone_number_id")

    return InternalInboundMessage(
        event_id=event.event_id,
        message_id=event.message_id,
        sender_id=event.sender_id,
        channel_user_id=event.sender_id,
        message_type=event.message_type or "unknown",
        text=event.text,
        phone_number_id=event.phone_number_id,
        timestamp=event.timestamp,
        metadata=event.metadata,
    )
