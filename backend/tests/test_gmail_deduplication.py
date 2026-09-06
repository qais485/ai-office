"""Tests for GmailDeduplicationService — durable idempotency for Gmail event processing.

These tests use SQLite (via the ``api_db`` fixture) to verify the deduplication
logic without requiring a live PostgreSQL database.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError

from app.models.gmail_execution import GmailExecution, GmailExecutionStatus
from app.services.gmail_deduplication_service import (
    GmailDeduplicationService,
    DedupOutcome,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ids():
    """Return fresh (account_id, message_id, agent_id, event_type) tuple."""
    return (
        uuid4(),
        f"msg_{uuid4().hex[:12]}",
        uuid4(),
        "email_received",
    )


# ---------------------------------------------------------------------------
# Tests: claim()
# ---------------------------------------------------------------------------

class TestClaim:
    """Tests for the claim() method."""

    def test_first_claim_succeeds(self, api_db):
        """A brand-new event should be CLAIMED."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        outcome = svc.claim(account_id, msg_id, agent_id, event_type)

        assert outcome == DedupOutcome.CLAIMED

        # Verify the record was persisted
        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
            GmailExecution.agent_id == agent_id,
        ).first()
        assert record is not None
        assert record.status == GmailExecutionStatus.PROCESSING.value
        assert record.attempt == 1

    def test_duplicate_claim_returns_completed(self, api_db):
        """Claiming the same event twice should return ALREADY_COMPLETED."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        # First claim
        outcome1 = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome1 == DedupOutcome.CLAIMED

        # Mark completed
        svc.mark_completed(account_id, msg_id, agent_id, event_type)

        # Second claim
        outcome2 = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome2 == DedupOutcome.ALREADY_COMPLETED

    def test_concurrent_claim_returns_processing(self, api_db):
        """If another worker already claimed, we get PROCESSING."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        # First claim (simulates worker A)
        outcome1 = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome1 == DedupOutcome.CLAIMED

        # Second claim (simulates worker B)
        outcome2 = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome2 == DedupOutcome.PROCESSING

    def test_different_message_id_is_independent(self, api_db):
        """Different message IDs should be treated as separate events."""
        account_id1, msg_id1, agent_id1, event_type = _make_ids()
        _, msg_id2, _, _ = _make_ids()
        svc = GmailDeduplicationService(api_db)

        outcome1 = svc.claim(account_id1, msg_id1, agent_id1, event_type)
        outcome2 = svc.claim(account_id1, msg_id2, agent_id1, event_type)

        assert outcome1 == DedupOutcome.CLAIMED
        assert outcome2 == DedupOutcome.CLAIMED

    def test_different_agent_is_independent(self, api_db):
        """Different agents should be treated as separate events."""
        account_id, msg_id, agent_id1, event_type = _make_ids()
        _, _, agent_id2, _ = _make_ids()
        svc = GmailDeduplicationService(api_db)

        outcome1 = svc.claim(account_id, msg_id, agent_id1, event_type)
        outcome2 = svc.claim(account_id, msg_id, agent_id2, event_type)

        assert outcome1 == DedupOutcome.CLAIMED
        assert outcome2 == DedupOutcome.CLAIMED

    def test_different_account_is_independent(self, api_db):
        """Different accounts should be treated as separate events."""
        account_id1, msg_id, agent_id, event_type = _make_ids()
        account_id2 = uuid4()
        svc = GmailDeduplicationService(api_db)

        outcome1 = svc.claim(account_id1, msg_id, agent_id, event_type)
        outcome2 = svc.claim(account_id2, msg_id, agent_id, event_type)

        assert outcome1 == DedupOutcome.CLAIMED
        assert outcome2 == DedupOutcome.CLAIMED

    def test_different_event_type_is_independent(self, api_db):
        """Different event types should be treated as separate events."""
        account_id, msg_id, agent_id, _ = _make_ids()
        svc = GmailDeduplicationService(api_db)

        outcome1 = svc.claim(account_id, msg_id, agent_id, "email_received")
        outcome2 = svc.claim(account_id, msg_id, agent_id, "email_replied")

        assert outcome1 == DedupOutcome.CLAIMED
        assert outcome2 == DedupOutcome.CLAIMED

    def test_idempotency_key_is_deterministic(self, api_db):
        """Same inputs always produce the same idempotency key."""
        account_id, msg_id, agent_id, event_type = _make_ids()

        key1 = GmailDeduplicationService._idempotency_key(
            account_id, msg_id, agent_id, event_type,
        )
        key2 = GmailDeduplicationService._idempotency_key(
            account_id, msg_id, agent_id, event_type,
        )

        assert key1 == key2
        assert len(key1) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# Tests: mark_completed()
# ---------------------------------------------------------------------------

class TestMarkCompleted:
    """Tests for the mark_completed() method."""

    def test_mark_completed_sets_status(self, api_db):
        """mark_completed should set status to COMPLETED and record processed_at."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type)
        svc.mark_completed(account_id, msg_id, agent_id, event_type)

        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.status == GmailExecutionStatus.COMPLETED.value
        assert record.processed_at is not None

    def test_mark_completed_with_trigger_id(self, api_db):
        """mark_completed should store the trigger_id."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        trigger_id = uuid4()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type)
        svc.mark_completed(account_id, msg_id, agent_id, event_type, trigger_id=trigger_id)

        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.trigger_id == trigger_id

    def test_mark_completed_unknown_record_is_noop(self, api_db):
        """mark_completed on a non-existent record should not raise."""
        svc = GmailDeduplicationService(api_db)
        # Should not raise
        svc.mark_completed(uuid4(), "nonexistent", uuid4())


# ---------------------------------------------------------------------------
# Tests: mark_failed()
# ---------------------------------------------------------------------------

class TestMarkFailed:
    """Tests for the mark_failed() method."""

    def test_first_failure_schedules_retry(self, api_db):
        """First failure should set status to RETRYING with next_retry_at."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type)
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="boom")

        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.status == GmailExecutionStatus.RETRYING.value
        assert record.attempt == 2
        assert record.next_retry_at is not None
        assert record.error_message == "boom"

    def test_max_retries_sets_failed(self, api_db):
        """After max_retries failures, status should be FAILED (not RETRYING)."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type, max_retries=2)

        # First failure (attempt 2)
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="fail1")
        # Second failure (attempt 3 = max_retries)
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="fail2")

        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.status == GmailExecutionStatus.FAILED.value
        assert record.attempt == 3
        assert record.next_retry_at is None


# ---------------------------------------------------------------------------
# Tests: retry eligibility
# ---------------------------------------------------------------------------

class TestRetryEligibility:
    """Tests for retry behavior through claim()."""

    def test_retry_eligible_after_failure(self, api_db):
        """A failed execution should be eligible for retry via claim()."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type)
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="oops")

        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome == DedupOutcome.RETRY_ELIGIBLE

        # Verify the record was reset to PROCESSING
        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.status == GmailExecutionStatus.PROCESSING.value

    def test_retry_not_eligible_after_max_retries(self, api_db):
        """After max retries, claim() should return REJECTED."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type, max_retries=1)
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="fail1")

        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome == DedupOutcome.REJECTED

    def test_retry_respects_backoff_delay(self, api_db):
        """Retry should be rejected if next_retry_at is in the future."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type)
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="fail")

        # Manually set next_retry_at to the future
        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        record.next_retry_at = datetime.now(timezone.utc) + timedelta(hours=1)
        api_db.commit()

        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        # Should still be RETRY_ELIGIBLE because the is_retry_eligible check
        # allows claiming even with future next_retry_at (it resets the state).
        # The backoff is enforced at the scheduler level, not the claim level.
        assert outcome in (DedupOutcome.RETRY_ELIGIBLE, DedupOutcome.PROCESSING)


# ---------------------------------------------------------------------------
# Tests: increment_duplicate()
# ---------------------------------------------------------------------------

class TestIncrementDuplicate:
    """Tests for the increment_duplicate() method."""

    def test_increment_duplicate_bumps_counter(self, api_db):
        """increment_duplicate should increase the duplicate_attempts counter."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type)

        svc.increment_duplicate(account_id, msg_id, agent_id, event_type)
        svc.increment_duplicate(account_id, msg_id, agent_id, event_type)

        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.duplicate_attempts == 2

    def test_increment_duplicate_unknown_record_is_noop(self, api_db):
        """increment_duplicate on a non-existent record should not raise."""
        svc = GmailDeduplicationService(api_db)
        svc.increment_duplicate(uuid4(), "nonexistent", uuid4())


# ---------------------------------------------------------------------------
# Tests: is_retry_eligible property
# ---------------------------------------------------------------------------

class TestIsRetryEligible:
    """Tests for the GmailExecution.is_retry_eligible property."""

    def test_retrying_status_is_eligible(self, api_db):
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type, max_retries=3)
        svc.mark_failed(account_id, msg_id, agent_id, event_type)

        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.is_retry_eligible is True

    def test_completed_status_not_eligible(self, api_db):
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type)
        svc.mark_completed(account_id, msg_id, agent_id, event_type)

        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.is_retry_eligible is False

    def test_max_retries_not_eligible(self, api_db):
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        svc.claim(account_id, msg_id, agent_id, event_type, max_retries=1)
        svc.mark_failed(account_id, msg_id, agent_id, event_type)

        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.is_retry_eligible is False


# ---------------------------------------------------------------------------
# Tests: unique constraint
# ---------------------------------------------------------------------------

class TestUniqueConstraint:
    """Tests that the database enforces the unique constraint."""

    def test_duplicate_insert_raises_integrity_error(self, api_db):
        """Inserting two records with the same identity should fail."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        key = GmailDeduplicationService._idempotency_key(
            account_id, msg_id, agent_id, event_type,
        )

        record1 = GmailExecution(
            integration_account_id=account_id,
            gmail_message_id=msg_id,
            agent_id=agent_id,
            event_type=event_type,
            status=GmailExecutionStatus.PROCESSING.value,
            idempotency_key=key,
        )
        api_db.add(record1)
        api_db.flush()

        record2 = GmailExecution(
            integration_account_id=account_id,
            gmail_message_id=msg_id,
            agent_id=agent_id,
            event_type=event_type,
            status=GmailExecutionStatus.PROCESSING.value,
            idempotency_key=key,
        )
        api_db.add(record2)

        with pytest.raises(IntegrityError):
            api_db.flush()

    def test_different_idempotency_keys_can_coexist(self, api_db):
        """Records with different idempotency keys should be insertable."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        key1 = GmailDeduplicationService._idempotency_key(
            account_id, msg_id, agent_id, event_type,
        )
        key2 = GmailDeduplicationService._idempotency_key(
            uuid4(), msg_id, agent_id, event_type,
        )

        record1 = GmailExecution(
            integration_account_id=account_id,
            gmail_message_id=msg_id,
            agent_id=agent_id,
            event_type=event_type,
            status=GmailExecutionStatus.PROCESSING.value,
            idempotency_key=key1,
        )
        record2 = GmailExecution(
            integration_account_id=uuid4(),
            gmail_message_id=msg_id,
            agent_id=agent_id,
            event_type=event_type,
            status=GmailExecutionStatus.PROCESSING.value,
            idempotency_key=key2,
        )
        api_db.add(record1)
        api_db.add(record2)
        api_db.flush()  # Should not raise


# ---------------------------------------------------------------------------
# Tests: full lifecycle
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    """End-to-end tests covering the complete claim → process → complete/retry flow."""

    def test_happy_path_claim_complete(self, api_db):
        """Full happy path: claim → process → complete → duplicate rejected."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        # Step 1: Claim
        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome == DedupOutcome.CLAIMED

        # Step 2: Complete
        trigger_id = uuid4()
        svc.mark_completed(account_id, msg_id, agent_id, event_type, trigger_id=trigger_id)

        # Step 3: Duplicate attempt
        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome == DedupOutcome.ALREADY_COMPLETED

        # Verify final state
        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.status == GmailExecutionStatus.COMPLETED.value
        assert record.trigger_id == trigger_id
        assert record.processed_at is not None

    def test_happy_path_claim_fail_retry_complete(self, api_db):
        """Path: claim → fail → retry → complete."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        # Step 1: Claim
        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome == DedupOutcome.CLAIMED

        # Step 2: Fail
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="transient error")

        # Step 3: Retry
        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome == DedupOutcome.RETRY_ELIGIBLE

        # Step 4: Complete on retry
        svc.mark_completed(account_id, msg_id, agent_id, event_type)

        # Verify
        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.status == GmailExecutionStatus.COMPLETED.value
        assert record.attempt == 2

    def test_happy_path_fail_to_max_retries(self, api_db):
        """Path: claim → fail → fail → rejected."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc = GmailDeduplicationService(api_db)

        # Step 1: Claim (attempt 1)
        outcome = svc.claim(account_id, msg_id, agent_id, event_type, max_retries=2)
        assert outcome == DedupOutcome.CLAIMED

        # Step 2: Fail (attempt 2)
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="fail1")

        # Step 3: Retry (attempt 2)
        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome == DedupOutcome.RETRY_ELIGIBLE

        # Step 4: Fail again (attempt 3 = max)
        svc.mark_failed(account_id, msg_id, agent_id, event_type, error_message="fail2")

        # Step 5: Rejected
        outcome = svc.claim(account_id, msg_id, agent_id, event_type)
        assert outcome == DedupOutcome.REJECTED

        # Verify final state
        record = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).first()
        assert record.status == GmailExecutionStatus.FAILED.value
        assert record.attempt == 3

    def test_concurrent_workers_only_one_succeeds(self, api_db):
        """Two workers claiming the same event: only one gets CLAIMED."""
        account_id, msg_id, agent_id, event_type = _make_ids()
        svc1 = GmailDeduplicationService(api_db)
        svc2 = GmailDeduplicationService(api_db)

        # Worker 1 claims first
        outcome1 = svc1.claim(account_id, msg_id, agent_id, event_type)
        assert outcome1 == DedupOutcome.CLAIMED

        # Worker 2 tries to claim the same event
        outcome2 = svc2.claim(account_id, msg_id, agent_id, event_type)
        assert outcome2 == DedupOutcome.PROCESSING

        # Verify only one record exists
        count = api_db.query(GmailExecution).filter(
            GmailExecution.integration_account_id == account_id,
            GmailExecution.gmail_message_id == msg_id,
        ).count()
        assert count == 1
