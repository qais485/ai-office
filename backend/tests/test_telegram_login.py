"""Tests for the Telegram Account interactive login flow.

Focus (Fix.md): the phone_code_hash returned by send_code_request() must be
persisted with the pending login state and passed to client.sign_in() during
verify_code — a fresh client cannot complete sign-in without it.
"""
import sys
import types
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.integration_service import IntegrationService
from app.services.telegram_login_service import (
    TelegramLoginError,
    TelegramLoginService,
    _pending,
)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Shadow conftest's SQLite fixture — these tests never touch the DB."""
    yield


# ---------------------------------------------------------------------------
# Fake Telethon layer (the service imports it lazily inside _load_telethon)
# ---------------------------------------------------------------------------

_integration_name_holder = {"name": "telegram_account"}


def _fake_get_integration(self, integration_id):
    """Stub preserving the real method's integration-name contract."""
    if _integration_name_holder["name"] != self.INTEGRATION_NAME:
        raise TelegramLoginError(
            "This login flow is only available for the Telegram Account integration"
        )
    return SimpleNamespace(name=_integration_name_holder["name"])


calls = {"send_code": [], "sign_in": []}
recorded_connects = []


class FakeSession:
    def __init__(self, payload=None):
        self._payload = payload or ""

    def save(self):
        return self._payload


class FakeMe:
    username = "tester"
    first_name = "Test"


class FakeSentCode:
    def __init__(self, phone_code_hash, code_length=5):
        self.phone_code_hash = phone_code_hash
        self.code_length = code_length


class FakeClient:
    behavior = {}

    def __init__(self, session, api_id, api_hash):
        self.session = session
        self.api_id = api_id
        self.api_hash = api_hash

    async def connect(self):
        # Simulate Telethon generating the auth key into the session on connect
        self.session._payload = self.session._payload or "TEMP_SESSION"
        return True

    async def disconnect(self):
        return True

    async def is_user_authorized(self):
        return bool(FakeClient.behavior.get("authorized"))

    async def send_code_request(self, phone):
        calls["send_code"].append(phone)
        return FakeSentCode(FakeClient.behavior.get("phone_code_hash", "HASH123"))

    async def sign_in(self, phone=None, code=None, password=None, phone_code_hash=None, **kw):
        calls["sign_in"].append(
            {"phone": phone, "code": code, "password": password, "phone_code_hash": phone_code_hash}
        )
        if FakeClient.behavior.get("password_needed") and password is None:
            raise FakeSessionPasswordNeeded()
        if FakeClient.behavior.get("fail_sign_in"):
            raise RuntimeError("PHONE_CODE_INVALID")
        self.session._payload = FakeClient.behavior.get("final_session", "FINAL_SESSION")
        return FakeMe()

    async def get_me(self):
        return FakeMe()


# Fake telethon.errors so the 2FA branch works even when real telethon
# is not installed in the test environment.
class FakeSessionPasswordNeeded(Exception):
    pass


_fake_telethon = types.ModuleType("telethon")
_fake_telethon.__path__ = []
_fake_errors = types.ModuleType("telethon.errors")
_fake_errors.SessionPasswordNeededError = FakeSessionPasswordNeeded
sys.modules.setdefault("telethon", _fake_telethon)
sys.modules.setdefault("telethon.errors", _fake_errors)


@pytest.fixture(autouse=True)
def _isolate_login_state(monkeypatch):
    """Fresh pending-state + fakes for every test."""
    _pending.clear()
    calls["send_code"].clear()
    calls["sign_in"].clear()
    recorded_connects.clear()
    FakeClient.behavior = {}
    _integration_name_holder["name"] = "telegram_account"
    monkeypatch.setattr(
        TelegramLoginService, "_load_telethon", staticmethod(lambda: (FakeClient, FakeSession))
    )
    monkeypatch.setattr(TelegramLoginService, "_get_integration", _fake_get_integration)

    def fake_connect_account(self, **kwargs):
        recorded_connects.append(kwargs)
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(IntegrationService, "connect_account", fake_connect_account)
    yield
    _pending.clear()


def _start(svc, user=None, integration=None):
    return svc.start_login(
        user or uuid4(), integration or uuid4(), "1234567", "a" * 32, "+98 912 345 6789"
    )


# ---------------------------------------------------------------------------
# start_login
# ---------------------------------------------------------------------------


class TestStartLogin:
    def test_returns_code_sent_with_normalized_phone(self):
        svc = TelegramLoginService(None)
        res = _start(svc)
        assert res["status"] == "code_sent"
        assert res["phone"] == "+989123456789"
        assert calls["send_code"] == ["+989123456789"]

    def test_pending_state_keeps_phone_code_hash_and_temp_session(self):
        svc = TelegramLoginService(None)
        _start(svc)
        assert len(_pending) == 1
        state = next(iter(_pending.values()))
        # THE Fix.md regression: the hash must be stored alongside temp_session
        assert state["phone_code_hash"] == "HASH123"
        assert state["temp_session"]
        assert state["password_required"] is False

    def test_invalid_phone_rejected_without_telethon_call(self):
        svc = TelegramLoginService(None)
        with pytest.raises(TelegramLoginError, match="phone number"):
            svc.start_login(uuid4(), uuid4(), "1234567", "a" * 32, "not-a-phone")
        assert calls["send_code"] == []
        assert _pending == {}

    def test_invalid_api_hash_rejected(self):
        svc = TelegramLoginService(None)
        with pytest.raises(TelegramLoginError, match="API Hash"):
            svc.start_login(uuid4(), uuid4(), "1234567", "nothex", "+989123456789")

    def test_wrong_integration_rejected(self):
        _integration_name_holder["name"] = "telegram"
        svc = TelegramLoginService(None)
        with pytest.raises(TelegramLoginError, match="Telegram Account"):
            _start(svc)
        assert calls["send_code"] == []


# ---------------------------------------------------------------------------
# verify_code
# ---------------------------------------------------------------------------


class TestVerifyCode:
    def test_passes_stored_phone_code_hash_to_sign_in(self):
        svc = TelegramLoginService(None)
        user, integration = uuid4(), uuid4()
        _start(svc, user, integration)

        res = svc.verify_code(user, integration, "12345")

        assert res["status"] == "connected"
        sent = calls["sign_in"][0]
        # THE Fix.md regression: the stored hash must reach sign_in
        assert sent["phone_code_hash"] == "HASH123"
        assert sent["code"] == "12345"
        assert sent["phone"] == "+989123456789"

    def test_success_stores_final_session_and_clears_state(self):
        svc = TelegramLoginService(None)
        user, integration = uuid4(), uuid4()
        _start(svc, user, integration)

        svc.verify_code(user, integration, "12345")

        assert len(recorded_connects) == 1
        creds = recorded_connects[0]["credentials"]
        assert creds["session"] == "FINAL_SESSION"
        assert creds["api_id"] == "1234567"
        assert creds["api_hash"] == "a" * 32
        assert _pending == {}

    def test_failed_code_attempt_keeps_state_for_retry(self):
        svc = TelegramLoginService(None)
        user, integration = uuid4(), uuid4()
        _start(svc, user, integration)
        FakeClient.behavior["fail_sign_in"] = True

        with pytest.raises(TelegramLoginError):
            svc.verify_code(user, integration, "99999")

        # state preserved between start and verify (retryable)
        assert len(_pending) == 1
        state = next(iter(_pending.values()))
        assert state["phone_code_hash"] == "HASH123"

        # retry with correct code succeeds using the same stored hash
        FakeClient.behavior["fail_sign_in"] = False
        res = svc.verify_code(user, integration, "12345")
        assert res["status"] == "connected"

    def test_missing_hash_in_state_rejected(self, monkeypatch):
        svc = TelegramLoginService(None)
        user, integration = uuid4(), uuid4()
        _start(svc, user, integration)
        for st in _pending.values():
            st["phone_code_hash"] = None

        with pytest.raises(TelegramLoginError, match="code hash"):
            svc.verify_code(user, integration, "12345")

    def test_no_pending_login_rejected(self):
        svc = TelegramLoginService(None)
        with pytest.raises(TelegramLoginError, match="No login in progress"):
            svc.verify_code(uuid4(), uuid4(), "12345")


# ---------------------------------------------------------------------------
# 2FA password step
# ---------------------------------------------------------------------------


class TestTwoFactorFlow:
    def test_code_then_password_completes_login(self):
        svc = TelegramLoginService(None)
        user, integration = uuid4(), uuid4()
        _start(svc, user, integration)
        FakeClient.behavior["password_needed"] = True

        res = svc.verify_code(user, integration, "12345")
        assert res == {"status": "2fa_required"}

        key = next(iter(_pending))
        assert _pending[key]["password_required"] is True
        assert _pending[key]["phone_code_hash"] == "HASH123"

        FakeClient.behavior["password_needed"] = False
        res = svc.verify_password(user, integration, "s3cret")

        assert res["status"] == "connected"
        assert calls["sign_in"][-1]["password"] == "s3cret"
        assert recorded_connects[0]["credentials"]["session"] == "FINAL_SESSION"
        assert _pending == {}

    def test_password_without_pending_login_rejected(self):
        svc = TelegramLoginService(None)
        with pytest.raises(TelegramLoginError, match="No login in progress"):
            svc.verify_password(uuid4(), uuid4(), "s3cret")

    def test_password_step_without_2fa_required_rejected(self):
        svc = TelegramLoginService(None)
        user, integration = uuid4(), uuid4()
        _start(svc, user, integration)
        with pytest.raises(TelegramLoginError, match="does not require a password"):
            svc.verify_password(user, integration, "s3cret")


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


class TestCancelLogin:
    def test_cancel_clears_pending_state(self):
        svc = TelegramLoginService(None)
        user, integration = uuid4(), uuid4()
        _start(svc, user, integration)

        assert svc.cancel_login(user, integration) == {"status": "cancelled"}
        assert _pending == {}

        with pytest.raises(TelegramLoginError, match="No login in progress"):
            svc.verify_code(user, integration, "12345")


# ---------------------------------------------------------------------------
# API endpoint wiring (no telethon needed: validation paths only)
# ---------------------------------------------------------------------------


class TestLoginEndpoints:
    """Endpoint wiring, isolated from app.main (no DB-backed lifespan/seed)."""

    @pytest.fixture(autouse=True)
    def _stub_integration_lookup(self, monkeypatch):
        monkeypatch.setattr(TelegramLoginService, "_get_integration", _fake_get_integration)

    def _make_client(self, include_user: bool = True):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.endpoints.integrations import router
        from app.database.session import get_db
        from app.api.deps import get_current_active_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/integrations")
        app.dependency_overrides[get_db] = lambda: None
        if include_user:
            app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=uuid4())
        return TestClient(app)

    def test_start_with_invalid_phone_returns_400(self):
        client = self._make_client()
        resp = client.post(
            f"/api/v1/integrations/accounts/telegram-login/start?integration_id={uuid4()}",
            json={"api_id": "1234567", "api_hash": "a" * 32, "phone": "bad"},
        )
        assert resp.status_code == 400
        assert "phone number" in resp.json()["detail"].lower()

    def test_start_rejects_wrong_integration(self):
        _integration_name_holder["name"] = "telegram"
        client = self._make_client()
        resp = client.post(
            f"/api/v1/integrations/accounts/telegram-login/start?integration_id={uuid4()}",
            json={"api_id": "1234567", "api_hash": "a" * 32, "phone": "+989123456789"},
        )
        assert resp.status_code == 400
        assert "Telegram Account" in resp.json()["detail"]

    def test_start_with_invalid_api_id_returns_400(self):
        client = self._make_client()
        resp = client.post(
            f"/api/v1/integrations/accounts/telegram-login/start?integration_id={uuid4()}",
            json={"api_id": "abc", "api_hash": "a" * 32, "phone": "+989123456789"},
        )
        assert resp.status_code == 400
        assert "API ID" in resp.json()["detail"]

    def test_verify_code_without_pending_login_returns_400(self):
        client = self._make_client()
        resp = client.post(
            f"/api/v1/integrations/accounts/telegram-login/verify-code?integration_id={uuid4()}",
            json={"code": "12345"},
        )
        assert resp.status_code == 400
        assert "No login in progress" in resp.json()["detail"]

    def test_cancel_without_pending_login_returns_cancelled(self):
        client = self._make_client()
        resp = client.post(
            f"/api/v1/integrations/accounts/telegram-login/cancel?integration_id={uuid4()}"
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "cancelled"}

    def test_login_requires_auth(self):
        client = self._make_client(include_user=False)
        resp = client.post(
            f"/api/v1/integrations/accounts/telegram-login/cancel?integration_id={uuid4()}"
        )
        assert resp.status_code == 401
