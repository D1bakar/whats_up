from app.core.config import Settings
from app.whatsapp.meta.client import HttpxTransport, MetaWhatsAppClient
from app.whatsapp.mock.provider import MockWhatsAppProvider
from app.whatsapp.provider import WhatsAppProvider
from app.whatsapp.transport import HttpTransport


def create_whatsapp_provider(
    settings: Settings,
    *,
    transport: HttpTransport | None = None,
) -> WhatsAppProvider:
    if settings.whatsapp_provider == "mock":
        return MockWhatsAppProvider()

    return MetaWhatsAppClient(
        settings,
        transport=transport or HttpxTransport(timeout=settings.meta_whatsapp_request_timeout),
    )
