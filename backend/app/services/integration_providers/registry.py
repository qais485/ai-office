"""Registry that maps integration names to provider implementations."""
from typing import Dict, Optional, Type

from app.services.integration_providers.base import IntegrationProvider


_registry: Dict[str, IntegrationProvider] = {}


def register_provider(provider: IntegrationProvider) -> None:
    _registry[provider.integration_name] = provider


def get_provider(name: str) -> Optional[IntegrationProvider]:
    return _registry.get(name)


def get_provider_registry() -> Dict[str, IntegrationProvider]:
    return dict(_registry)


def _load_builtin_providers() -> None:
    """Lazily import and register all built-in providers."""
    if _registry:
        return

    from app.services.integration_providers.gmail import GmailProvider
    from app.services.integration_providers.google_calendar import GoogleCalendarProvider
    from app.services.integration_providers.google_drive import GoogleDriveProvider
    from app.services.integration_providers.slack import SlackProvider
    from app.services.integration_providers.telegram import TelegramProvider
    from app.services.integration_providers.instagram import InstagramProvider

    for provider_cls in (
        GmailProvider,
        GoogleCalendarProvider,
        GoogleDriveProvider,
        SlackProvider,
        TelegramProvider,
        InstagramProvider,
    ):
        register_provider(provider_cls())


# Ensure providers are loaded on first access
_load_builtin_providers()
