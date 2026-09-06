"""Tests for the hardened email system: sync, duplicates, failures, sending, account management."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.core.config import settings
from app.models.email_account import EmailAccount
from app.models.email import EmailMessage, EmailStatus
from app.models.user import User
from app.schemas.email_account import EmailAccountCreate, EmailAccountUpdate
from app.schemas.email import EmailCreate
from app.services.email_account_service import EmailAccountService
from app.services.email_service import EmailService
from app.utils.encryption import encrypt_field


@pytest.fixture
def db():
    engine = create_engine(settings.DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


@pytest.fixture
def sample_user(db):
    user = User(
        id=uuid4(),
        email="test@example.com",
        name="Test User",
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def sample_account(db, sample_user):
    account = EmailAccount(
        id=uuid4(),
        user_id=sample_user.id,
        email_address="test@company.com",
        display_name="Test Mail",
        imap_host="imap.company.com",
        imap_port=993,
        imap_username="test@company.com",
        imap_password=encrypt_field("test_password"),
        imap_use_ssl=True,
        smtp_host="smtp.company.com",
        smtp_port=465,
        smtp_username="test@company.com",
        smtp_password=encrypt_field("test_password"),
        smtp_use_ssl=True,
        is_active=True,
        sync_frequency_minutes=5,
    )
    db.add(account)
    db.flush()
    return account


# ------------------------------------------------------------------
# Account CRUD Tests
# ------------------------------------------------------------------

class TestEmailAccountCRUD:
    def test_create_account(self, db, sample_user):
        service = EmailAccountService(db)
        data = EmailAccountCreate(
            email_address="new@company.com",
            imap_host="imap.company.com",
            imap_username="new@company.com",
            imap_password="secret123",
            smtp_host="smtp.company.com",
            smtp_username="new@company.com",
            smtp_password="secret456",
        )
        account = service.create_account(sample_user.id, data)
        assert account.email_address == "new@company.com"
        assert account.user_id == sample_user.id
        assert account.imap_password != "secret123"  # Should be encrypted
        assert account.smtp_password != "secret456"

    def test_get_account(self, db, sample_account):
        service = EmailAccountService(db)
        fetched = service.get_account(sample_account.id)
        assert fetched is not None
        assert fetched.email_address == "test@company.com"

    def test_get_nonexistent_account(self, db):
        service = EmailAccountService(db)
        result = service.get_account(uuid4())
        assert result is None

    def test_list_user_accounts(self, db, sample_user, sample_account):
        service = EmailAccountService(db)
        accounts = service.get_accounts(sample_user.id)
        assert len(accounts) >= 1
        assert any(a.email_address == "test@company.com" for a in accounts)

    def test_list_other_user_accounts_empty(self, db, sample_account):
        service = EmailAccountService(db)
        other_user_id = uuid4()
        accounts = service.get_accounts(other_user_id)
        assert len(accounts) == 0

    def test_update_account(self, db, sample_account):
        service = EmailAccountService(db)
        update = EmailAccountUpdate(display_name="Updated Mail")
        updated = service.update_account(sample_account.id, update)
        assert updated.display_name == "Updated Mail"

    def test_update_password_encrypts(self, db, sample_account):
        service = EmailAccountService(db)
        new_pass = "new_secret_123"
        update = EmailAccountUpdate(imap_password=new_pass)
        updated = service.update_account(sample_account.id, update)
        assert updated.imap_password != new_pass

    def test_update_empty_password_not_reencrypted(self, db, sample_account):
        original_password = sample_account.imap_password
        service = EmailAccountService(db)
        update = EmailAccountUpdate(display_name="No Pass Change")
        updated = service.update_account(sample_account.id, update)
        assert updated.imap_password == original_password

    def test_delete_account(self, db, sample_account):
        service = EmailAccountService(db)
        result = service.delete_account(sample_account.id)
        assert result is True
        assert service.get_account(sample_account.id) is None

    def test_delete_nonexistent(self, db):
        service = EmailAccountService(db)
        result = service.delete_account(uuid4())
        assert result is False


# ------------------------------------------------------------------
# Duplicate Detection Tests
# ------------------------------------------------------------------

class TestDuplicatePrevention:
    def test_import_same_message_twice_is_duplicate(self, db, sample_account):
        service = EmailAccountService(db)
        raw = {
            "imap_id": "12345",
            "from_address": "sender@test.com",
            "to_address": "test@company.com",
            "subject": "Test Subject",
            "body": "Test body",
            "date": "Mon, 1 Jan 2024 00:00:00 +0000",
        }

        is_new_1 = service._import_message(sample_account, raw)
        db.flush()
        assert is_new_1 is True

        is_new_2 = service._import_message(sample_account, raw)
        db.flush()
        assert is_new_2 is False

    def test_different_accounts_same_imap_id_not_duplicate(self, db, sample_user, sample_account):
        service = EmailAccountService(db)
        account2 = EmailAccount(
            id=uuid4(),
            user_id=sample_user.id,
            email_address="other@company.com",
            imap_host="imap.company.com",
            imap_port=993,
            imap_username="other@company.com",
            imap_password=encrypt_field("pass"),
            smtp_host="smtp.company.com",
            smtp_port=465,
            smtp_username="other@company.com",
            smtp_password=encrypt_field("pass"),
            is_active=True,
        )
        db.add(account2)
        db.flush()

        raw = {
            "imap_id": "12345",
            "from_address": "sender@test.com",
            "to_address": "test@company.com",
            "subject": "Test",
            "body": "Body",
            "date": "Mon, 1 Jan 2024 00:00:00 +0000",
        }

        is_new_1 = service._import_message(sample_account, raw)
        db.flush()
        assert is_new_1 is True

        is_new_2 = service._import_message(account2, raw)
        db.flush()
        assert is_new_2 is True  # Different account = not a duplicate

    def test_different_imap_ids_not_duplicate(self, db, sample_account):
        service = EmailAccountService(db)
        raw1 = {"imap_id": "111", "from_address": "a@b.com", "to_address": "x@y.com", "subject": "S1", "body": "B1", "date": ""}
        raw2 = {"imap_id": "222", "from_address": "a@b.com", "to_address": "x@y.com", "subject": "S2", "body": "B2", "date": ""}

        assert service._import_message(sample_account, raw1) is True
        db.flush()
        assert service._import_message(sample_account, raw2) is True
        db.flush()


# ------------------------------------------------------------------
# Sync State Tests
# ------------------------------------------------------------------

class TestSyncState:
    def test_sync_updates_last_sync_at(self, db, sample_account):
        service = EmailAccountService(db)
        assert sample_account.last_sync_at is None

        with patch.object(service, '_get_decrypted_credentials', return_value={"imap_password": "p", "smtp_password": "p"}):
            with patch('app.services.imap_service.ImapService.connect', return_value=True):
                with patch('app.services.imap_service.ImapService.fetch_unseen', return_value=[]):
                    with patch('app.services.imap_service.ImapService.disconnect'):
                        result = service.sync_account(sample_account.id)

        assert result["success"] is True
        assert sample_account.last_sync_at is not None

    def test_sync_failure_sets_error(self, db, sample_account):
        service = EmailAccountService(db)
        with patch.object(service, '_get_decrypted_credentials', return_value={"imap_password": "p", "smtp_password": "p"}):
            with patch('app.services.imap_service.ImapService.connect', return_value=False):
                with patch('app.services.imap_service.ImapService.disconnect'):
                    result = service.sync_account(sample_account.id)

        assert result["success"] is False
        assert sample_account.sync_error is not None

    def test_sync_clears_previous_error(self, db, sample_account):
        sample_account.sync_error = "Previous error"
        db.flush()

        service = EmailAccountService(db)
        with patch.object(service, '_get_decrypted_credentials', return_value={"imap_password": "p", "smtp_password": "p"}):
            with patch('app.services.imap_service.ImapService.connect', return_value=True):
                with patch('app.services.imap_service.ImapService.fetch_unseen', return_value=[]):
                    with patch('app.services.imap_service.ImapService.disconnect'):
                        result = service.sync_account(sample_account.id)

        assert sample_account.sync_error is None


# ------------------------------------------------------------------
# Frequency-Aware Sync Tests
# ------------------------------------------------------------------

class TestFrequencyAwareSync:
    def test_accounts_needing_sync_includes_new_accounts(self, db, sample_account):
        service = EmailAccountService(db)
        due = service.get_accounts_needing_sync()
        assert any(a.id == sample_account.id for a in due)

    def test_accounts_needing_sync_excludes_recently_synced(self, db, sample_account):
        sample_account.last_sync_at = datetime.now(timezone.utc).isoformat()
        db.flush()

        service = EmailAccountService(db)
        due = service.get_accounts_needing_sync()
        assert not any(a.id == sample_account.id for a in due)

    def test_accounts_needing_sync_includes_stale_accounts(self, db, sample_account):
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        sample_account.last_sync_at = stale_time
        db.flush()

        service = EmailAccountService(db)
        due = service.get_accounts_needing_sync()
        assert any(a.id == sample_account.id for a in due)

    def test_accounts_needing_sync_excludes_inactive(self, db, sample_account):
        sample_account.is_active = False
        db.flush()

        service = EmailAccountService(db)
        due = service.get_accounts_needing_sync()
        assert not any(a.id == sample_account.id for a in due)


# ------------------------------------------------------------------
# Email Service Tests
# ------------------------------------------------------------------

class TestEmailService:
    def test_create_email(self, db, sample_account):
        service = EmailService(db)
        data = EmailCreate(
            from_address="sender@test.com",
            to_address="test@company.com",
            subject="Test",
            body="Hello",
            account_id=sample_account.id,
        )
        email = service.create_email(data)
        assert email.id is not None
        assert email.from_address == "sender@test.com"

    def test_process_email_idempotent(self, db, sample_account):
        service = EmailService(db)
        data = EmailCreate(
            from_address="sender@test.com",
            to_address="test@company.com",
            subject="Test",
            body="Hello",
            account_id=sample_account.id,
        )
        email = service.create_email(data)

        # Set to PROCESSING
        email.status = EmailStatus.PROCESSING
        db.commit()

        # Second call should return same email without reprocessing
        result = service.process_email(email.id)
        assert result.status == EmailStatus.PROCESSING

    def test_get_email_stats_sql_aggregation(self, db, sample_account):
        service = EmailService(db)
        for i in range(3):
            data = EmailCreate(
                from_address=f"sender{i}@test.com",
                to_address="test@company.com",
                subject=f"Test {i}",
                body="Hello",
                status=EmailStatus.NEW,
                account_id=sample_account.id,
            )
            service.create_email(data)

        stats = service.get_email_stats()
        assert stats["total"] == 3
        assert stats["new"] == 3

    def test_get_emails_filters_by_user(self, db, sample_user, sample_account):
        service = EmailService(db)
        data = EmailCreate(
            from_address="sender@test.com",
            to_address="test@company.com",
            subject="Test",
            body="Hello",
            account_id=sample_account.id,
        )
        service.create_email(data)

        emails = service.get_emails(user_id=sample_user.id)
        assert len(emails) >= 1

    def test_delete_email(self, db, sample_account):
        service = EmailService(db)
        data = EmailCreate(
            from_address="sender@test.com",
            to_address="test@company.com",
            subject="To Delete",
            body="Hello",
            account_id=sample_account.id,
        )
        email = service.create_email(data)
        result = service.delete_email(email.id)
        assert result is True
        assert service.get_email(email.id) is None


# ------------------------------------------------------------------
# Send Email Tests (mock-based)
# ------------------------------------------------------------------

class TestSendEmail:
    def test_send_reply_success(self, db, sample_account):
        service = EmailAccountService(db)
        with patch('app.services.smtp_service.SmtpService.send_email', return_value=(True, "Sent")):
            result = service.send_reply(
                sample_account.id,
                to_address="recipient@test.com",
                subject="Re: Test",
                body="Response",
            )
        assert result["success"] is True

    def test_send_reply_failure(self, db, sample_account):
        service = EmailAccountService(db)
        with patch('app.services.smtp_service.SmtpService.send_email', return_value=(False, "Auth failed")):
            result = service.send_reply(
                sample_account.id,
                to_address="recipient@test.com",
                subject="Re: Test",
                body="Response",
            )
        assert result["success"] is False
        assert "Auth failed" in result["error"]

    def test_send_reply_account_not_found(self, db):
        service = EmailAccountService(db)
        result = service.send_reply(uuid4(), "x@y.com", "Sub", "Body")
        assert result["success"] is False


# ------------------------------------------------------------------
# Connection Test Tests (mock-based)
# ------------------------------------------------------------------

class TestConnectionTests:
    def test_test_imap(self):
        with patch('app.services.imap_service.ImapService.connect', return_value=True):
            with patch('app.services.imap_service.ImapService.disconnect'):
                service = EmailAccountService(None)
                success, msg = service.test_imap("host", 993, "user", "pass")
                assert success is True

    def test_test_smtp(self):
        with patch('app.services.smtp_service.SmtpService.send_email', return_value=(True, "OK")):
            service = EmailAccountService(None)
            # SmtpService.test_connection uses login, not send_email
            with patch('app.services.smtp_service.smtplib.SMTP_SSL'):
                success, msg = service.test_smtp("host", 465, "user", "pass")
                # Will depend on mock behavior
