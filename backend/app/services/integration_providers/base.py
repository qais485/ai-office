"""Abstract base class for integration providers.

Each integration (Gmail, Slack, etc.) implements this interface so the
ToolExecutionService can invoke any integration action uniformly.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProviderResult:
    """Standardised result from a provider action execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


class IntegrationProvider(ABC):
    """Base class that every integration provider must implement."""

    @property
    @abstractmethod
    def integration_name(self) -> str:
        """Return the canonical integration name (e.g. 'gmail', 'slack')."""
        ...

    @abstractmethod
    async def execute_action(
        self,
        action: str,
        parameters: Dict[str, Any],
        access_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """Execute a single action against the external service.

        Parameters
        ----------
        action:
            The action name (e.g. ``send_email``, ``read_events``).
        parameters:
            Action-specific payload.
        access_token:
            Decrypted OAuth2 access token (if the integration uses OAuth2).
        credentials:
            Decrypted API-key / bot-token credentials (if the integration
            uses ``api_key`` or ``bot_token`` auth).

        Returns
        -------
        ProviderResult
        """
        ...

    @abstractmethod
    async def test_connection(
        self,
        access_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """Verify that the supplied credentials / tokens are still valid."""
        ...

    @abstractmethod
    async def revoke(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """Revoke tokens or disconnect from the provider (best-effort)."""
        ...
