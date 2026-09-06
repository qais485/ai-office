"""Hardened email account service with atomic sync, duplicate protection, and logging."""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone

from app.models.email_account import EmailAccount
from app.models.email import EmailMessage, EmailStatus
from app.schemas.email_account import EmailAccountCreate, EmailAccountUpdate
from app.services.imap_service import ImapService
from app.services.smtp_service import SmtpService
from app.utils.encryption import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)


class EmailAccountService:
    def __init__(self, db: Session):
        self.db = db

    def get_accounts(self, user_id: UUID) -> List[EmailAccount]:
        return self.db.query(EmailAccount).filter(
            EmailAccount.user_id == user_id,
            EmailAccount.is_active == True,
        ).all()

    def get_account(self, account_id: UUID) -> Optional[EmailAccount]:
        return self.db.query(EmailAccount).filter(EmailAccount.id == account_id).first()

    def create_account(self, user_id: UUID, data: EmailAccountCreate) -> EmailAccount:
        account = EmailAccount(
            user_id=user_id,
            email_address=data.email_address,
            display_name=data.display_name,
            imap_host=data.imap_host,
            imap_port=data.imap_port or 993,
            imap_username=data.imap_username,
            imap_password=encrypt_field(data.imap_password),
            imap_use_ssl=data.imap_use_ssl if data.imap_use_ssl is not None else True,
            smtp_host=data.smtp_host,
            smtp_port=data.smtp_port or 465,
            smtp_username=data.smtp_username,
            smtp_password=encrypt_field(data.smtp_password),
            smtp_use_ssl=data.smtp_use_ssl if data.smtp_use_ssl is not None else True,
            sync_frequency_minutes=data.sync_frequency_minutes or 5,
            is_active=True,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        logger.info(f"Email account created: {data.email_address} for user {user_id}")
        return account

    def update_account(self, account_id: UUID, data: EmailAccountUpdate) -> Optional[EmailAccount]:
        account = self.get_account(account_id)
        if not account:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Only re-encrypt passwords if they are new (not already encrypted)
        if "imap_password" in update_data and update_data["imap_password"]:
            update_data["imap_password"] = encrypt_field(update_data["imap_password"])
        elif "imap_password" in update_data:
            del update_data["imap_password"]

        if "smtp_password" in update_data and update_data["smtp_password"]:
            update_data["smtp_password"] = encrypt_field(update_data["smtp_password"])
        elif "smtp_password" in update_data:
            del update_data["smtp_password"]

        for key, value in update_data.items():
            setattr(account, key, value)

        self.db.commit()
        self.db.refresh(account)
        logger.info(f"Email account updated: {account.email_address}")
        return account

    def delete_account(self, account_id: UUID) -> bool:
        account = self.get_account(account_id)
        if not account:
            return False
        self.db.delete(account)
        self.db.commit()
        logger.info(f"Email account deleted: {account.email_address}")
        return True

    def sync_account(self, account_id: UUID) -> dict:
        """Sync emails from IMAP for a single account. Atomic with duplicate protection."""
        account = self.get_account(account_id)
        if not account:
            return {"success": False, "error": "Account not found"}

        creds = self._get_decrypted_credentials(account)
        if not creds:
            return {"success": False, "error": "Invalid credentials"}

        imap = ImapService(
            host=account.imap_host,
            port=account.imap_port,
            username=account.imap_username,
            password=creds["imap_password"],
            use_ssl=account.imap_use_ssl,
        )

        try:
            if not imap.connect():
                account.sync_error = "IMAP connection failed"
                self.db.commit()
                return {"success": False, "error": "IMAP connection failed"}

            raw_messages = imap.fetch_unseen(limit=50)
            new_count = 0
            duplicate_count = 0

            for raw in raw_messages:
                is_new = self._import_message(account, raw)
                if is_new:
                    new_count += 1
                else:
                    duplicate_count += 1

            # Single atomic commit for all emails + sync state
            account.last_sync_at = datetime.now(timezone.utc).isoformat()
            account.sync_error = None
            self.db.commit()

            logger.info(
                f"Email sync complete for {account.email_address}: "
                f"{new_count} new, {duplicate_count} duplicates"
            )
            return {
                "success": True,
                "new_emails": new_count,
                "duplicates": duplicate_count,
                "total_fetched": len(raw_messages),
            }
        except Exception as e:
            logger.error(f"Email sync failed for {account.email_address}: {e}")
            account.sync_error = str(e)[:500]
            self.db.commit()
            return {"success": False, "error": str(e)}
        finally:
            imap.disconnect()

    def _import_message(self, account: EmailAccount, raw: dict) -> bool:
        """Import a single email message. Returns True if new, False if duplicate.

        Race-safe: relies on the unique index uq_email_messages_account_conversation
        (account_id, conversation_id) instead of a non-atomic SELECT-then-INSERT.
        A concurrent sync inserting the same message first raises IntegrityError,
        which we treat as "already imported" — no event, no agent reply.
        """
        from sqlalchemy.exc import IntegrityError

        try:
            email_msg = EmailMessage(
                from_address=raw["from_address"],
                to_address=raw["to_address"],
                subject=raw["subject"],
                body=raw["body"],
                status=EmailStatus.NEW,
                conversation_id=raw["imap_id"],
                account_id=account.id,
            )
            self.db.add(email_msg)
            self.db.flush()
        except IntegrityError:
            # Same message was imported by a concurrent sync (manual + scheduled
            # poll racing). Roll back only this insert, keep the outer transaction.
            self.db.rollback()
            return False

        # Emit EMAIL_RECEIVED event to trigger agent processing
        self._emit_email_received_event(account, email_msg, raw)

        return True

    def _emit_email_received_event(self, account: EmailAccount, email_msg: EmailMessage, raw: dict) -> None:
        """Emit an EMAIL_RECEIVED event for agent triggering."""
        try:
            from app.events.types import EventType, EmailEvent
            from app.events.bus import event_bus
            import asyncio

            event = EmailEvent(
                email_id=str(email_msg.id),
                from_address=raw.get("from_address", ""),
                subject=raw.get("subject", ""),
                account_id=str(account.id),
            )

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(event_bus.publish(event))
                else:
                    loop.run_until_complete(event_bus.publish(event))
            except RuntimeError:
                asyncio.run(event_bus.publish(event))

        except Exception as e:
            logger.warning(f"Failed to emit EMAIL_RECEIVED event: {e}", exc_info=True)

    def send_reply(self, account_id: UUID, to_address: str, subject: str, body: str) -> dict:
        account = self.get_account(account_id)
        if not account:
            return {"success": False, "error": "Account not found"}

        creds = self._get_decrypted_credentials(account)
        if not creds:
            return {"success": False, "error": "Invalid credentials"}

        smtp = SmtpService(
            host=account.smtp_host,
            port=account.smtp_port,
            username=account.smtp_username,
            password=creds["smtp_password"],
            use_ssl=account.smtp_use_ssl,
        )

        success, message = smtp.send_email(
            to_address=to_address,
            subject=subject,
            body=body,
            from_address=account.email_address,
        )
        return {"success": success, "error": message if not success else None}

    def _get_decrypted_credentials(self, account: EmailAccount) -> Optional[dict]:
        try:
            return {
                "imap_password": decrypt_field(account.imap_password) if account.imap_password else "",
                "smtp_password": decrypt_field(account.smtp_password) if account.smtp_password else "",
            }
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for {account.email_address}: {e}")
            return None

    def test_imap(self, host: str, port: int, username: str, password: str, use_ssl: bool = True) -> tuple[bool, str]:
        service = ImapService(host, port, username, password, use_ssl)
        return service.test_connection()

    def test_smtp(self, host: str, port: int, username: str, password: str, use_ssl: bool = True) -> tuple[bool, str]:
        service = SmtpService(host, port, username, password, use_ssl)
        return service.test_connection()

    def get_accounts_needing_sync(self) -> List[EmailAccount]:
        """Get all active accounts that are due for sync based on their frequency."""
        now = datetime.now(timezone.utc)
        accounts = self.db.query(EmailAccount).filter(
            EmailAccount.is_active == True,
        ).all()

        due = []
        for account in accounts:
            if not account.last_sync_at:
                due.append(account)
                continue
            try:
                last_sync = datetime.fromisoformat(account.last_sync_at)
                if last_sync.tzinfo is None:
                    last_sync = last_sync.replace(tzinfo=timezone.utc)
                freq = account.sync_frequency_minutes or 5
                if (now - last_sync).total_seconds() >= freq * 60:
                    due.append(account)
            except (ValueError, TypeError):
                due.append(account)

        return due
