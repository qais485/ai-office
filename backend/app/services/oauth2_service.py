import hashlib
import hmac
import json
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.utils.encryption import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)

META_GRAPH_API = "https://graph.facebook.com/v18.0"


def _get_config_value(key: str) -> Optional[str]:
    """Look up a config value by key name from the settings object."""
    return getattr(settings, key, None)


def _resolve_redirect_uri(integration: Integration) -> str:
    """Resolve the OAuth2 redirect URI for an integration.

    Uses GOOGLE_OAUTH_REDIRECT_URI if set (must point to the backend
    callback endpoint, e.g. http://localhost:8000/api/v1/integrations/oauth2/callback).
    Falls back to the backend callback path derived from the API prefix.
    """
    if settings.GOOGLE_OAUTH_REDIRECT_URI:
        return settings.GOOGLE_OAUTH_REDIRECT_URI
    return f"{settings.FRONTEND_URL}{settings.API_V1_PREFIX}/integrations/oauth2/callback"


def _sign_state(data: dict) -> str:
    """Create a signed state parameter using HMAC."""
    payload = json.dumps(data, sort_keys=True, default=str)
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    encoded = secrets.token_urlsafe(len(payload))[:len(payload)]  # pad for length
    # Use base64 encoding for the payload
    import base64
    b64_payload = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{b64_payload}.{sig}"


def _verify_state(state: str) -> Optional[dict]:
    """Verify and decode a signed state parameter."""
    try:
        import base64
        b64_payload, sig = state.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(b64_payload.encode()).decode()

        # Verify signature
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]

        if not hmac.compare_digest(sig, expected_sig):
            logger.warning("OAuth2 state signature mismatch")
            return None

        return json.loads(payload)
    except Exception as e:
        logger.error(f"Failed to verify OAuth2 state: {e}")
        return None


class OAuth2Service:
    def __init__(self, db: Session):
        self.db = db

    def get_authorization_url(self, integration: Integration, user_id: UUID) -> str:
        """Generate the OAuth2 authorization URL with a signed state parameter."""
        if not integration.oauth2_authorize_url:
            raise ValueError(f"Integration {integration.name} does not have OAuth2 configured")

        client_id = _get_config_value(integration.oauth2_client_id_key) if integration.oauth2_client_id_key else None
        if not client_id:
            raise ValueError(f"Client ID not configured for {integration.name}")

        # Create signed state
        state_data = {
            "user_id": str(user_id),
            "integration_id": str(integration.id),
            "integration_name": integration.name,
            "nonce": secrets.token_hex(8),
        }
        state = _sign_state(state_data)

        # Build redirect URI
        redirect_uri = _resolve_redirect_uri(integration)

        # Build authorization URL
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }

        if integration.oauth2_scopes:
            # Different providers use different scope separators
            if "slack.com" in (integration.oauth2_authorize_url or ""):
                params["scope"] = integration.oauth2_scopes
            else:
                params["scope"] = integration.oauth2_scopes

        # Allow providers to add extra params (e.g., Google needs access_type=offline for refresh tokens)
        if "google.com" in (integration.oauth2_authorize_url or ""):
            params["access_type"] = "offline"
            params["prompt"] = "consent"

        # Facebook silently SKIPS permissions that were already granted (or
        # previously declined) in an earlier consent — so when new scopes are
        # added to an existing connection, the dialog may not ask for them at
        # all and the token ends up without them (symptom: /me/accounts → 0
        # pages). auth_type=rerequest forces the dialog to re-ask those.
        if "facebook.com" in (integration.oauth2_authorize_url or ""):
            params["auth_type"] = "rerequest"
            logger.info(
                "OAuth2 authorize URL for %s requests scopes: %s",
                integration.name,
                integration.oauth2_scopes,
            )

        separator = "&" if "?" in integration.oauth2_authorize_url else "?"
        return f"{integration.oauth2_authorize_url}{separator}{urlencode(params)}"

    async def exchange_code(self, code: str, state: str) -> Tuple[Optional[IntegrationAccount], Optional[str]]:
        """
        Exchange an authorization code for tokens and create/update the integration account.
        Returns (account, error_message).
        """
        # Verify state
        state_data = _verify_state(state)
        if not state_data:
            return None, "Invalid or expired state parameter"

        user_id = UUID(state_data["user_id"])
        integration_id = UUID(state_data["integration_id"])

        # Get integration
        integration = self.db.query(Integration).filter(Integration.id == integration_id).first()
        if not integration:
            return None, "Integration not found"

        # Get client credentials
        client_id = _get_config_value(integration.oauth2_client_id_key) if integration.oauth2_client_id_key else None
        client_secret = _get_config_value(integration.oauth2_client_secret_key) if integration.oauth2_client_secret_key else None

        if not client_id or not client_secret:
            return None, f"OAuth2 client credentials not configured for {integration.name}"

        # Build redirect URI (must match the one used in authorization)
        redirect_uri = _resolve_redirect_uri(integration)

        # Exchange code for tokens
        token_url = integration.oauth2_token_url
        if not token_url:
            return None, f"Token URL not configured for {integration.name}"

        token_data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=token_data, timeout=30.0)
                response.raise_for_status()
                token_response = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Token exchange failed for {integration.name}: {e.response.status_code} - {e.response.text}")
            return None, f"Token exchange failed: {e.response.status_code}"
        except Exception as e:
            logger.error(f"Token exchange error for {integration.name}: {e}")
            return None, f"Token exchange error: {str(e)}"

        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in")
        scope = token_response.get("scope", integration.oauth2_scopes)

        if not access_token:
            error = token_response.get("error_description", token_response.get("error", "No access token received"))
            return None, error

        # Calculate token expiry
        token_expiry = None
        if expires_in:
            token_expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

        # --- Instagram: detect the authorized account before saving anything ---
        ig_profile: Optional[dict] = None
        stored_token = access_token
        if integration.name == "instagram":
            ig_profile, ig_error = await self._detect_instagram_account(
                access_token,
                client_id=client_id,
                client_secret=client_secret,
            )
            if ig_error:
                return None, ig_error
            logger.info(
                "Instagram account detected: username=%s ig_user_id=%s page=%s",
                ig_profile.get("username"),
                ig_profile.get("ig_user_id"),
                ig_profile.get("facebook_page_name"),
            )
            # Instagram Graph API calls (posting, comments, insights) require a
            # PAGE access token — store it (encrypted) as this account's
            # credential instead of the short-lived user token. Page tokens
            # derived from a long-lived user token do not expire.
            stored_token = ig_profile.pop("page_access_token", None) or access_token
            token_expiry = None  # page tokens carry no meaningful expiry

        # Encrypt tokens
        encrypted_access = encrypt_field(stored_token)
        encrypted_refresh = encrypt_field(refresh_token) if refresh_token else None

        # Upsert integration account
        existing = self.db.query(IntegrationAccount).filter(
            IntegrationAccount.user_id == user_id,
            IntegrationAccount.integration_id == integration_id,
            IntegrationAccount.is_active == True
        ).first()

        display_name = self._instagram_display_name(ig_profile) or integration.display_name

        if existing:
            existing.oauth2_access_token = encrypted_access
            existing.oauth2_refresh_token = encrypted_refresh
            existing.oauth2_token_expiry = token_expiry
            existing.oauth2_scope = scope
            existing.status = "connected"
            existing.display_name = display_name
            if ig_profile:
                self._apply_instagram_profile(existing, ig_profile)
            account = existing
        else:
            account = IntegrationAccount(
                integration_id=integration_id,
                user_id=user_id,
                display_name=display_name,
                status="connected",
                is_active=True,
                oauth2_access_token=encrypted_access,
                oauth2_refresh_token=encrypted_refresh,
                oauth2_token_expiry=token_expiry,
                oauth2_scope=scope,
            )
            if ig_profile:
                self._apply_instagram_profile(account, ig_profile)
            self.db.add(account)

        self.db.commit()
        self.db.refresh(account)
        return account, None

    @staticmethod
    def _instagram_display_name(ig_profile: Optional[dict]) -> Optional[str]:
        """Build the account display name from a detected Instagram profile."""
        if not ig_profile:
            return None
        username = ig_profile.get("username")
        return f"@{username}" if username else None

    @staticmethod
    def _apply_instagram_profile(account: IntegrationAccount, ig_profile: dict) -> None:
        """Persist the detected Instagram identity on the integration account."""
        config = dict(account.config or {})
        config.update(
            {
                "instagram_user_id": ig_profile.get("ig_user_id"),
                "username": ig_profile.get("username"),
                "name": ig_profile.get("name"),
                "account_type": ig_profile.get("account_type"),
                "media_count": ig_profile.get("media_count"),
                "facebook_page_id": ig_profile.get("facebook_page_id"),
                "facebook_page_name": ig_profile.get("facebook_page_name"),
                "connected_via": "facebook_oauth",
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        account.config = config
        # The profile fetch is the first successful sync of this connection.
        account.last_sync_at = datetime.now(timezone.utc).isoformat()

    async def _detect_instagram_account(
        self,
        access_token: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        """Discover the Instagram Professional account behind a Facebook OAuth grant.

        Flow: user access token → (long-lived exchange) → /me/accounts (Pages +
        linked IG accounts) → Page access token → /{ig_user_id} profile.

        Returns (profile, error). On success the profile dict carries
        ``page_access_token`` — the caller MUST pop it and store it ENCRYPTED as
        the account credential (Instagram Graph API calls require a Page access
        token, not the user token). It must never be logged or persisted raw.

        Security: never log access tokens, secrets or codes — only IDs/names.
        """
        import httpx

        def _safe_graph_error(resp_json) -> str:
            """Extract a short, token-free error summary from a Graph error body."""
            try:
                err = (resp_json or {}).get("error") or {}
                code = err.get("code", "?")
                subcode = err.get("error_subcode", "-")
                msg = str(err.get("message", "no message"))[:200]
                return f"code={code} subcode={subcode} message={msg}"
            except Exception:
                return "unparseable error body"

        try:
            async with httpx.AsyncClient() as client:
                working_token = access_token

                # ── 0) Long-lived user token (best-effort) ────────────────
                # Code-exchange tokens expire in ~1-2h. A Page access token
                # derived from a LONG-LIVED user token does not expire — that
                # is what the integration needs for later API calls.
                if client_id and client_secret:
                    try:
                        ex_resp = await client.get(
                            f"{META_GRAPH_API}/oauth/access_token",
                            params={
                                "grant_type": "fb_exchange_token",
                                "client_id": client_id,
                                "client_secret": client_secret,
                                "fb_exchange_token": access_token,
                            },
                            timeout=20.0,
                        )
                        if ex_resp.status_code == 200:
                            ex_body = ex_resp.json() or {}
                            if ex_body.get("access_token"):
                                working_token = ex_body["access_token"]
                                logger.info(
                                    "Instagram detection: exchanged for long-lived user token (expires_in=%s)",
                                    ex_body.get("expires_in", "no-expiry"),
                                )
                            else:
                                logger.warning(
                                    "Instagram detection: long-lived exchange returned no access_token: %s",
                                    _safe_graph_error(ex_body),
                                )
                        else:
                            logger.warning(
                                "Instagram detection: long-lived exchange failed HTTP %s: %s — continuing with the code-exchange token",
                                ex_resp.status_code,
                                _safe_graph_error(ex_resp.json()),
                            )
                    except Exception as ex_err:
                        logger.warning(
                            "Instagram detection: long-lived exchange error: %s — continuing with the code-exchange token",
                            ex_err,
                        )

                # ── 0b) Introspect the GRANTED permissions ────────────────
                # /me/permissions shows what the token can ACTUALLY do — the
                # consent dialog can silently omit permissions (skipped on
                # re-consent, or unchecked by the user). This is the ground
                # truth for the "0 pages" symptom. Logs permission NAMES only.
                perms_resp = await client.get(
                    f"{META_GRAPH_API}/me/permissions",
                    params={"access_token": working_token},
                    timeout=20.0,
                )
                granted: list[str] = []
                if perms_resp.status_code == 200:
                    granted = [
                        item.get("permission")
                        for item in ((perms_resp.json() or {}).get("data") or [])
                        if item.get("status") == "granted" and item.get("permission")
                    ]
                    logger.info(
                        "Instagram detection: granted permissions (%d): %s",
                        len(granted),
                        ", ".join(sorted(granted)) or "(none)",
                    )
                else:
                    logger.warning(
                        "Instagram detection: /me/permissions failed HTTP %s: %s",
                        perms_resp.status_code,
                        _safe_graph_error(perms_resp.json()),
                    )

                if "pages_show_list" not in granted:
                    logger.error(
                        "Instagram detection: pages_show_list is NOT granted on this token — "
                        "/me/accounts will return zero pages. Fix: disconnect, then connect again "
                        "and ACCEPT the 'Manage your Pages' step in the Facebook dialog "
                        "(auth_type=rerequest now forces the dialog to re-ask it). "
                        "Also verify in Meta App Dashboard → App Review that "
                        "pages_show_list/pages_read_engagement/instagram_basic exist for the app."
                    )
                if "instagram_basic" not in granted:
                    logger.error(
                        "Instagram detection: instagram_basic is NOT granted — Instagram Graph "
                        "fields (username, media_count) will be unreadable even if a Page links an IG account."
                    )

                # ── 1) All Pages the user granted access to ──────────────
                # Requires pages_show_list. WITHOUT that scope this returns an
                # EMPTY data array even when the user administers many Pages —
                # that was the reason "no linked Instagram account" appeared
                # despite the account being linked in Meta's UI.
                pages_resp = await client.get(
                    f"{META_GRAPH_API}/me/accounts",
                    params={
                        "fields": "id,name,instagram_business_account{id,username}",
                        "access_token": working_token,
                    },
                    timeout=20.0,
                )
                pages_body = pages_resp.json() if pages_resp.status_code == 200 else None
                if pages_resp.status_code != 200:
                    logger.error(
                        "Instagram detection: /me/accounts failed HTTP %s: %s",
                        pages_resp.status_code,
                        _safe_graph_error(pages_body or pages_resp.json()),
                    )
                    pages_resp.raise_for_status()

                pages = (pages_body or {}).get("data", []) or []
                logger.info(
                    "Instagram detection: /me/accounts returned %d page(s)", len(pages)
                )
                if not pages and "pages_show_list" in granted:
                    logger.error(
                        "Instagram detection: pages_show_list IS granted but /me/accounts still returned 0 pages — "
                        "Meta-app side issue. Check: (1) the Facebook user is admin/developer/tester of the app "
                        "while it is in Development mode; (2) the user has a role (admin/editor) on the Pages; "
                        "(3) Business verification / Advanced Access status in App Review; "
                        "(4) the app is not restricted by platform/region settings."
                    )

                # ── 2) Check EVERY page, not just the first one ───────────
                for page in pages:
                    page_id = page.get("id")
                    page_name = page.get("name", "(unnamed)")
                    ig_biz = page.get("instagram_business_account") or {}
                    ig_id = ig_biz.get("id")

                    if not ig_id:
                        logger.info(
                            "Instagram detection: page %s (%s) has no linked Instagram account",
                            page_id,
                            page_name,
                        )
                        continue

                    logger.info(
                        "Instagram detection: page %s (%s) has linked Instagram account ig_user_id=%s username=%s",
                        page_id,
                        page_name,
                        ig_id,
                        ig_biz.get("username", "?"),
                    )

                    # ── 3) Fetch the IG profile with the PAGE access token ──
                    # The user access token cannot read Instagram Graph fields;
                    # only the Page access token of the page that owns the IG
                    # account can. Ask Graph for the page token explicitly.
                    page_token_resp = await client.get(
                        f"{META_GRAPH_API}/{page_id}",
                        params={"fields": "access_token", "access_token": working_token},
                        timeout=20.0,
                    )
                    if page_token_resp.status_code != 200:
                        logger.warning(
                            "Instagram detection: could not get page access token for page %s: HTTP %s: %s",
                            page_id,
                            page_token_resp.status_code,
                            _safe_graph_error(page_token_resp.json()),
                        )
                        continue
                    page_token = (page_token_resp.json() or {}).get("access_token")
                    if not page_token:
                        logger.warning(
                            "Instagram detection: page %s returned no access_token field", page_id
                        )
                        continue

                    prof_resp = await client.get(
                        f"{META_GRAPH_API}/{ig_id}",
                        params={
                            "fields": "id,username,name,account_type,media_count,profile_picture_url",
                            "access_token": page_token,
                        },
                        timeout=20.0,
                    )
                    if prof_resp.status_code != 200:
                        logger.warning(
                            "Instagram detection: profile fetch for ig_user_id %s via page %s failed: HTTP %s: %s",
                            ig_id,
                            page_id,
                            prof_resp.status_code,
                            _safe_graph_error(prof_resp.json()),
                        )
                        continue

                    profile = prof_resp.json() or {}
                    profile["ig_user_id"] = profile.get("id")
                    profile["facebook_page_id"] = page_id
                    profile["facebook_page_name"] = page_name
                    profile["page_access_token"] = page_token  # caller pops & encrypts
                    logger.info(
                        "Instagram detection: SUCCESS username=%s account_type=%s media_count=%s via page %s (%s)",
                        profile.get("username"),
                        profile.get("account_type"),
                        profile.get("media_count"),
                        page_id,
                        page_name,
                    )
                    return profile, None

                # Every page was checked; none has a linked IG professional account
                logger.warning(
                    "Instagram detection: checked %d page(s) — none has a linked Instagram Professional account. "
                    "If your account IS linked: the app needs pages_show_list + instagram_basic scopes, "
                    "the IG account must be Business/Creator, and the Meta app must have Instagram Graph API product added.",
                    len(pages),
                )
                return None, (
                    "No Instagram Professional (Business/Creator) account is linked to your "
                    "Facebook pages. Convert your Instagram account to Professional, link it "
                    "to a Facebook Page, then connect again."
                )
        except httpx.HTTPStatusError as e:
            try:
                err_summary = _safe_graph_error(e.response.json())
            except Exception:
                err_summary = e.response.text[:200]
            logger.error(
                "Meta Graph API error during Instagram detection: HTTP %s: %s",
                e.response.status_code,
                err_summary,
            )
            return None, f"Meta Graph API error {e.response.status_code}: could not verify your Instagram account"
        except Exception as e:
            logger.error("Instagram account detection failed: %s", e, exc_info=True)
            return None, f"Could not detect your Instagram account: {str(e)[:200]}"

    def get_access_token(self, account: IntegrationAccount) -> Optional[str]:
        """Decrypt and return the access token for an account."""
        if not account.oauth2_access_token:
            return None
        return decrypt_field(account.oauth2_access_token)

    def get_refresh_token(self, account: IntegrationAccount) -> Optional[str]:
        """Decrypt and return the refresh token for an account."""
        if not account.oauth2_refresh_token:
            return None
        return decrypt_field(account.oauth2_refresh_token)

    async def refresh_access_token(self, account: IntegrationAccount) -> Optional[str]:
        """Refresh the access token using the refresh token."""
        refresh_token = self.get_refresh_token(account)
        if not refresh_token:
            return None

        integration = self.db.query(Integration).filter(Integration.id == account.integration_id).first()
        if not integration or not integration.oauth2_token_url:
            return None

        client_id = _get_config_value(integration.oauth2_client_id_key) if integration.oauth2_client_id_key else None
        client_secret = _get_config_value(integration.oauth2_client_secret_key) if integration.oauth2_client_secret_key else None

        if not client_id or not client_secret:
            return None

        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(integration.oauth2_token_url, data=token_data, timeout=30.0)
                response.raise_for_status()
                token_response = response.json()
        except Exception as e:
            logger.error(f"Token refresh failed for {integration.name}: {e}")
            return None

        access_token = token_response.get("access_token")
        expires_in = token_response.get("expires_in")

        if not access_token:
            return None

        account.oauth2_access_token = encrypt_field(access_token)
        if expires_in:
            account.oauth2_token_expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        self.db.commit()

        return access_token
