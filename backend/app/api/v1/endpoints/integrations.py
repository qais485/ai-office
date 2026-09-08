from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.integration import (
    IntegrationCreate, IntegrationResponse,
    IntegrationAccountCreate, IntegrationAccountUpdate, IntegrationAccountResponse,
    ConnectRequest, OAuth2AuthorizeResponse,
    TelegramLoginStartRequest, TelegramLoginCodeRequest, TelegramLoginPasswordRequest
)
from app.services.integration_service import IntegrationService
from app.services.oauth2_service import OAuth2Service
from app.services.telegram_login_service import TelegramLoginService, TelegramLoginError
from app.api.deps import get_current_active_user
from app.models.user import User
from app.core.config import settings

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[IntegrationResponse])
async def get_integrations(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    return service.get_integrations(active_only=active_only)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    integration = service.get_integration(integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.post("/", response_model=IntegrationResponse)
async def create_integration(
    integration: IntegrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    created = service.create_integration(integration)
    logger.info("Created integration %s", created.id)
    return created


@router.get("/accounts/", response_model=list[IntegrationAccountResponse])
async def get_user_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    return service.get_user_accounts(current_user.id)


@router.get("/accounts/{account_id}", response_model=IntegrationAccountResponse)
async def get_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Integration account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this account")
    return account


@router.post("/accounts/", response_model=IntegrationAccountResponse, status_code=201)
async def create_account(
    data: IntegrationAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    return service.create_account(current_user.id, data)


@router.post("/accounts/connect", response_model=IntegrationAccountResponse, status_code=201)
async def connect_account(
    integration_id: UUID,
    data: ConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    result = service.connect_account(
        user_id=current_user.id,
        integration_id=integration_id,
        credentials=data.credentials,
        display_name=data.display_name,
        config=data.config
    )
    logger.info("Connected integration %s for user %s", integration_id, current_user.id)
    return result


@router.post("/accounts/disconnect")
async def disconnect_account(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    success = service.disconnect_account(current_user.id, integration_id)
    if not success:
        raise HTTPException(status_code=404, detail="Integration account not found")
    logger.info("Disconnected integration %s for user %s", integration_id, current_user.id)
    return {"detail": "Integration disconnected"}


# --- Telegram Account interactive login (api_id + api_hash -> code -> 2FA) ---

@router.post("/accounts/telegram-login/start")
async def telegram_login_start(
    integration_id: UUID,
    data: TelegramLoginStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = TelegramLoginService(db)
    try:
        return service.start_login(current_user.id, integration_id, data.api_id, data.api_hash, data.phone)
    except TelegramLoginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/accounts/telegram-login/verify-code")
async def telegram_login_verify_code(
    integration_id: UUID,
    data: TelegramLoginCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = TelegramLoginService(db)
    try:
        return service.verify_code(current_user.id, integration_id, data.code)
    except TelegramLoginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/accounts/telegram-login/verify-password")
async def telegram_login_verify_password(
    integration_id: UUID,
    data: TelegramLoginPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = TelegramLoginService(db)
    try:
        return service.verify_password(current_user.id, integration_id, data.password)
    except TelegramLoginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/accounts/telegram-login/cancel")
async def telegram_login_cancel(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = TelegramLoginService(db)
    try:
        return service.cancel_login(current_user.id, integration_id)
    except TelegramLoginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/accounts/{account_id}", response_model=IntegrationAccountResponse)
async def update_account(
    account_id: UUID,
    data: IntegrationAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    updated = service.update_account(account_id, data)
    logger.info("Updated integration account %s", account_id)
    return updated


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Integration account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this account")
    service.delete_account(account_id)
    logger.info("Deleted integration account %s", account_id)
    return {"detail": "Integration account deleted"}


@router.get("/agent/{agent_id}", response_model=list[IntegrationResponse])
async def get_agent_integrations(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    return service.get_agent_integrations(agent_id, user_id=current_user.id)


@router.post("/agent/{agent_id}/assign", response_model=dict)
async def assign_integration_to_agent(
    agent_id: UUID,
    integration_id: UUID,
    capabilities: Optional[List[str]] = None,
    integration_account_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    result = service.assign_integration_to_agent(
        agent_id, integration_id, capabilities, integration_account_id, user_id=current_user.id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Agent or integration not found")
    return {"detail": "Integration assigned to agent", "id": str(result.id)}


@router.delete("/agent/{agent_id}/remove")
async def remove_integration_from_agent(
    agent_id: UUID,
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    success = service.remove_integration_from_agent(agent_id, integration_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent integration assignment not found")
    return {"detail": "Integration removed from agent"}


@router.get("/{integration_id}/agents", response_model=list[dict])
async def get_integration_agents(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = IntegrationService(db)
    agents = service.get_integration_agents(integration_id, user_id=current_user.id)
    return [{"id": str(a.id), "name": a.name, "role": a.role} for a in agents]


@router.get("/{integration_id}/oauth2/authorize", response_model=OAuth2AuthorizeResponse)
async def get_oauth2_authorize_url(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get the OAuth2 authorization URL for an integration."""
    integration_service = IntegrationService(db)
    integration = integration_service.get_integration(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    if integration.auth_type != "oauth2":
        raise HTTPException(status_code=400, detail="Integration does not use OAuth2 authentication")

    if not integration.oauth2_authorize_url:
        raise HTTPException(status_code=400, detail="OAuth2 not configured for this integration")

    oauth2_service = OAuth2Service(db)
    try:
        auth_url = oauth2_service.get_authorization_url(integration, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return OAuth2AuthorizeResponse(authorization_url=auth_url, state="ok")


@router.get("/oauth2/callback")
async def oauth2_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle OAuth2 callback from provider. Exchanges code for tokens and redirects to frontend."""
    frontend_callback = f"{settings.FRONTEND_URL}/integrations/callback"

    if error:
        return RedirectResponse(
            url=f"{frontend_callback}?status=error&message={error}",
            status_code=302
        )

    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_callback}?status=error&message=Missing+authorization+code+or+state",
            status_code=302
        )

    oauth2_service = OAuth2Service(db)
    account, exchange_error = await oauth2_service.exchange_code(code, state)

    if exchange_error:
        return RedirectResponse(
            url=f"{frontend_callback}?status=error&message={exchange_error}",
            status_code=302
        )

    # Auto-create GmailSyncState for Gmail integrations so monitoring starts
    from app.models.integration import Integration
    from app.models.gmail_sync_state import GmailSyncState
    integration = db.query(Integration).filter(Integration.id == account.integration_id).first()
    if integration and integration.name == "gmail":
        existing_state = db.query(GmailSyncState).filter(
            GmailSyncState.integration_account_id == account.id,
        ).first()
        if not existing_state:
            sync_state = GmailSyncState(
                integration_account_id=account.id,
                user_id=account.user_id,
                is_active=True,
                processed_message_ids=[],
                total_processed=0,
                consecutive_errors=0,
            )
            db.add(sync_state)
            db.commit()
            logger.info("Auto-created GmailSyncState for account %s", account.id)

    redirect_url = f"{frontend_callback}?status=success&account_id={account.id}"
    username = (account.config or {}).get("username")
    if username:
        from urllib.parse import quote

        redirect_url += f"&username={quote(str(username))}"

    return RedirectResponse(
        url=redirect_url,
        status_code=302
    )


# ------------------------------------------------------------------
# NEW: connection status, token refresh, disconnect with revoke
# ------------------------------------------------------------------

@router.get("/accounts/{account_id}/status")
async def get_connection_status(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Check whether an integration account's credentials / tokens are still valid."""
    service = IntegrationService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Integration account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    integration = service.get_integration(account.integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration definition not found")

    from app.services.integration_providers.registry import get_provider
    provider = get_provider(integration.name)

    if not provider:
        return {"status": account.status, "provider_available": False, "message": "No provider for this integration"}

    oauth2_service = OAuth2Service(db)
    access_token = oauth2_service.get_access_token(account) if account.oauth2_access_token else None
    credentials = None
    if account.credentials:
        from app.utils.encryption import decrypt_field
        credentials = {k: decrypt_field(str(v)) for k, v in account.credentials.items()}

    import asyncio
    from app.utils.async_utils import run_async

    async def _test():
        return await provider.test_connection(access_token=access_token, credentials=credentials)

    try:
        result = run_async(_test())
    except Exception as e:
        logger.error(f"Connection test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "provider_available": False,
            "error": str(e),
        }

    return {
        "status": account.status,
        "provider_available": True,
        "connected": result.success,
        "error": result.error,
        "data": result.data,
        "token_expiry": account.oauth2_token_expiry,
    }


@router.post("/accounts/{account_id}/refresh-token")
async def refresh_token(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Manually refresh the OAuth2 access token for an account."""
    service = IntegrationService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Integration account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not account.oauth2_refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")

    oauth2_service = OAuth2Service(db)
    import asyncio
    from app.utils.async_utils import run_async

    async def _refresh():
        return await oauth2_service.refresh_access_token(account)

    try:
        new_token = run_async(_refresh())
    except Exception as e:
        logger.error(f"Token refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Token refresh failed – tokens may be revoked")

    if not new_token:
        raise HTTPException(status_code=400, detail="Token refresh failed – tokens may be revoked")

    db.refresh(account)
    return {"detail": "Token refreshed", "token_expiry": account.oauth2_token_expiry}


@router.post("/accounts/{account_id}/disconnect-revoke")
async def disconnect_and_revoke(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Disconnect an integration and attempt to revoke its tokens with the provider."""
    service = IntegrationService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Integration account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    integration = service.get_integration(account.integration_id)
    revoke_ok = True
    revoke_msg = ""

    if integration:
        from app.services.integration_providers.registry import get_provider
        provider = get_provider(integration.name)
        if provider:
            oauth2_service = OAuth2Service(db)
            access_token = oauth2_service.get_access_token(account) if account.oauth2_access_token else None
            refresh_token_val = oauth2_service.get_refresh_token(account) if account.oauth2_refresh_token else None
            credentials = None
            if account.credentials:
                from app.utils.encryption import decrypt_field
                credentials = {k: decrypt_field(str(v)) for k, v in account.credentials.items()}

            import asyncio
            from app.utils.async_utils import run_async

            async def _revoke():
                return await provider.revoke(access_token=access_token, refresh_token=refresh_token_val, credentials=credentials)

            try:
                rev_result = run_async(_revoke())
            except Exception as e:
                logger.error(f"Token revoke failed: {e}", exc_info=True)
                revoke_ok = False
                revoke_msg = str(e)

            revoke_ok = rev_result.success
            revoke_msg = rev_result.error or ""

    success = service.disconnect_account(current_user.id, account.integration_id)
    logger.info("Disconnected and revoked integration %s for user %s", account.integration_id, current_user.id)
    return {"detail": "Integration disconnected and tokens revoked", "revoke_ok": revoke_ok, "revoke_message": revoke_msg}
