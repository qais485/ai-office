"""GmailDeduplicationService — durable idempotency for Gmail-triggered agent work.

This service replaces the ad-hoc in-memory dedup checks that previously lived
inside ``GmailMonitorService._process_message``.  It uses a database table
(``gmail_executions``) with a **unique constraint** on the composite identity
key so that:

* Duplicate rows cannot be inserted (database-level protection).
* Concurrent workers see each other's in-progress records.
* Failed attempts are tracked and eligible for controlled retry.
* Restarting the application does not lose dedup state.

Typical usage inside ``GmailMonitorService``::

    dedup = GmailDeduplicationService(db)
    for agent in linked_agents:
        outcome = dedup.claim(
            integration_account_id=account.id,
            gmail_message_id=msg_id,
            agent_id=agent.id,
            event_type="email_received",
        )
        if outcome == DedupOutcome.ALREADY_COMPLETED:
            logger.debug("Already processed, skipping")
            continue
        if outcome == DedupOutcome.PROCESSING:
            logger.debug("Another worker is processing, skipping")
            continue
        if outcome == DedupOutcome.RETRY_ELIGIBLE:
            logger.info("Previous attempt failed, retrying")
        # outcome == DedupOutcome.CLAIMED → proceed with processing
        ...
        dedup.mark_completed(execution)
"""
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.gmail_execution import GmailExecution, GmailExecutionStatus

logger = logging.getLogger(__name__)

# Exponential back-off: 2^attempt seconds, capped at 1 hour
_RETRY_BASE_SECONDS = 2
_RETRY_CAP_SECONDS = 3600


class DedupOutcome(str, Enum):
    """Result of a ``claim()`` call."""
    CLAIMED = "claimed"              # caller may proceed
    ALREADY_COMPLETED = "completed"  # duplicate, already done
    PROCESSING = "processing"        # another worker holds the lock
    RETRY_ELIGIBLE = "retrying"      # prior failure, retry allowed
    REJECTED = "rejected"            # max retries exceeded


class GmailDeduplicationService:
    """Database-backed idempotency layer for Gmail event processing."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @staticmethod
    def _idempotency_key(
        integration_account_id: UUID,
        gmail_message_id: str,
        agent_id: UUID,
        event_type: str,
    ) -> str:
        """Deterministic SHA-256 hash used as the unique constraint value."""
        raw = f"{integration_account_id}:{gmail_message_id}:{agent_id}:{event_type}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Claim
    # ------------------------------------------------------------------

    def claim(
        self,
        integration_account_id: UUID,
        gmail_message_id: str,
        agent_id: UUID,
        event_type: str = "email_received",
        max_retries: int = 3,
    ) -> DedupOutcome:
        """Attempt to claim processing rights for one (account, msg, agent) tuple.

        Returns a ``DedupOutcome`` indicating whether the caller should proceed.

        The method is safe under concurrency because the unique index on
        ``idempotency_key`` causes the second ``INSERT`` to raise
        ``IntegrityError``, which we catch and translate into the appropriate
        outcome.
        """
        key = self._idempotency_key(
            integration_account_id, gmail_message_id, agent_id, event_type,
        )

        now = datetime.now(timezone.utc)

        # ── 1. Check existing record ──────────────────────────────────
        existing: Optional[GmailExecution] = (
            self.db.query(GmailExecution)
            .filter(GmailExecution.idempotency_key == key)
            .first()
        )

        if existing is not None:
            return self._handle_existing(existing, now)

        # ── 2. Insert new record (claim the slot) ─────────────────────
        record = GmailExecution(
            integration_account_id=integration_account_id,
            gmail_message_id=gmail_message_id,
            agent_id=agent_id,
            event_type=event_type,
            status=GmailExecutionStatus.PROCESSING.value,
            idempotency_key=key,
            attempt=1,
            max_retries=max_retries,
        )
        self.db.add(record)

        try:
            self.db.flush()  # triggers the unique constraint check
        except IntegrityError:
            # Another worker inserted between our SELECT and INSERT.
            self.db.rollback()
            # Re-query to find what the other worker inserted.
            existing = (
                self.db.query(GmailExecution)
                .filter(GmailExecution.idempotency_key == key)
                .first()
            )
            if existing is not None:
                logger.debug(
                    "Concurrent claim detected, delegating to existing record",
                    extra={"idempotency_key": key[:16], "agent_id": str(agent_id)},
                )
                return self._handle_existing(existing, now)
            # Should never happen, but be defensive.
            return DedupOutcome.REJECTED

        self.db.commit()
        logger.info(
            "Gmail execution claimed",
            extra={
                "idempotency_key": key[:16],
                "agent_id": str(agent_id),
                "message_id": gmail_message_id,
            },
        )
        return DedupOutcome.CLAIMED

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def mark_completed(
        self,
        integration_account_id: UUID,
        gmail_message_id: str,
        agent_id: UUID,
        event_type: str = "email_received",
        trigger_id: Optional[UUID] = None,
    ) -> None:
        """Mark the execution as successfully completed."""
        key = self._idempotency_key(
            integration_account_id, gmail_message_id, agent_id, event_type,
        )
        record = self.db.query(GmailExecution).filter(
            GmailExecution.idempotency_key == key,
        ).first()

        if record is None:
            logger.warning(
                "mark_completed called for unknown execution",
                extra={"idempotency_key": key[:16]},
            )
            return

        record.status = GmailExecutionStatus.COMPLETED.value
        record.trigger_id = trigger_id
        record.processed_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(
            "Gmail execution completed",
            extra={
                "idempotency_key": key[:16],
                "agent_id": str(agent_id),
                "attempt": record.attempt,
            },
        )

    def mark_failed(
        self,
        integration_account_id: UUID,
        gmail_message_id: str,
        agent_id: UUID,
        event_type: str = "email_received",
        error_message: str = "",
    ) -> None:
        """Mark the execution as failed and schedule a retry if eligible."""
        key = self._idempotency_key(
            integration_account_id, gmail_message_id, agent_id, event_type,
        )
        record = self.db.query(GmailExecution).filter(
            GmailExecution.idempotency_key == key,
        ).first()

        if record is None:
            logger.warning(
                "mark_failed called for unknown execution",
                extra={"idempotency_key": key[:16]},
            )
            return

        record.attempt += 1
        record.error_message = error_message[:2000]

        if record.attempt < record.max_retries:
            delay = min(_RETRY_BASE_SECONDS ** record.attempt, _RETRY_CAP_SECONDS)
            record.status = GmailExecutionStatus.RETRYING.value
            record.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            logger.info(
                "Gmail execution failed, scheduled retry",
                extra={
                    "idempotency_key": key[:16],
                    "attempt": record.attempt,
                    "retry_in_seconds": delay,
                },
            )
        else:
            record.status = GmailExecutionStatus.FAILED.value
            record.next_retry_at = None
            logger.warning(
                "Gmail execution failed, max retries exhausted",
                extra={"idempotency_key": key[:16], "attempt": record.attempt},
            )

        self.db.commit()

    def increment_duplicate(
        self,
        integration_account_id: UUID,
        gmail_message_id: str,
        agent_id: UUID,
        event_type: str = "email_received",
    ) -> None:
        """Bump the duplicate-attempts counter for observability."""
        key = self._idempotency_key(
            integration_account_id, gmail_message_id, agent_id, event_type,
        )
        record = self.db.query(GmailExecution).filter(
            GmailExecution.idempotency_key == key,
        ).first()

        if record is not None:
            record.duplicate_attempts = (record.duplicate_attempts or 0) + 1
            self.db.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_existing(self, record: GmailExecution, now: datetime) -> DedupOutcome:
        """Map an existing record's status to a ``DedupOutcome``."""
        status = record.status

        if status == GmailExecutionStatus.COMPLETED.value:
            logger.debug(
                "Duplicate Gmail event rejected (already completed)",
                extra={"idempotency_key": record.idempotency_key[:16], "agent_id": str(record.agent_id)},
            )
            return DedupOutcome.ALREADY_COMPLETED

        if status == GmailExecutionStatus.PROCESSING.value:
            logger.debug(
                "Duplicate Gmail event rejected (currently processing)",
                extra={"idempotency_key": record.idempotency_key[:16], "agent_id": str(record.agent_id)},
            )
            return DedupOutcome.PROCESSING

        if status in (
            GmailExecutionStatus.FAILED.value,
            GmailExecutionStatus.RETRYING.value,
        ):
            if record.is_retry_eligible:
                # Reset to processing so the caller can retry.
                record.status = GmailExecutionStatus.PROCESSING.value
                record.attempt += 1
                if record.next_retry_at:
                    record.next_retry_at = None
                self.db.commit()
                logger.info(
                    "Retrying failed Gmail execution",
                    extra={
                        "idempotency_key": record.idempotency_key[:16],
                        "attempt": record.attempt,
                    },
                )
                return DedupOutcome.RETRY_ELIGIBLE
            else:
                logger.debug(
                    "Failed Gmail execution not retry-eligible",
                    extra={
                        "idempotency_key": record.idempotency_key[:16],
                        "attempt": record.attempt,
                        "max_retries": record.max_retries,
                    },
                )
                return DedupOutcome.REJECTED

        # PENDING status — claim it by moving to processing.
        if status == GmailExecutionStatus.PENDING.value:
            record.status = GmailExecutionStatus.PROCESSING.value
            self.db.commit()
            return DedupOutcome.CLAIMED

        return DedupOutcome.REJECTED
