"""Tests for database connection resilience — retry logic and session lifecycle.

These tests verify:
1. The retry decorator handles transient errors correctly.
2. The get_db() dependency rolls back on error.
3. The engine configuration is valid.
4. Pool status logging works.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError, DisconnectionError

from app.database.session import get_db, engine, SessionLocal, check_db_health


class TestDbRetryDecorator:
    """Tests for the db_retry decorator."""

    def test_retry_succeeds_on_first_attempt(self):
        """Should succeed without retries when no error occurs."""
        from app.database.retry import db_retry

        call_count = 0

        @db_retry(max_retries=3, base_delay=0.01)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_succeeds_after_transient_error(self):
        """Should retry on OperationalError and succeed."""
        from app.database.retry import db_retry

        call_count = 0

        @db_retry(max_retries=3, base_delay=0.01)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError(
                    "SSL SYSCALL error: EOF detected",
                    {},
                    Exception("connection lost"),
                )
            return "recovered"

        result = flaky_func()
        assert result == "recovered"
        assert call_count == 3

    def test_retry_exhausted_raises_original_error(self):
        """Should raise the last error after max retries."""
        from app.database.retry import db_retry

        @db_retry(max_retries=2, base_delay=0.01)
        def failing_func():
            raise OperationalError(
                "SSL SYSCALL error: EOF detected",
                {},
                Exception("connection lost"),
            )

        with pytest.raises(OperationalError):
            failing_func()

    def test_retry_does_not_catch_non_retryable_errors(self):
        """Should not retry non-OperationalError exceptions."""
        from app.database.retry import db_retry

        call_count = 0

        @db_retry(max_retries=3, base_delay=0.01)
        def value_error_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("not a DB error")

        with pytest.raises(ValueError):
            value_error_func()
        assert call_count == 1  # No retries

    def test_retry_exhausted_message_error(self):
        """Should retry on 'remaining connection slots' error."""
        from app.database.retry import db_retry

        call_count = 0

        @db_retry(max_retries=2, base_delay=0.01)
        def connection_limit_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OperationalError(
                    "remaining connection slots are reserved",
                    {},
                    Exception("connection limit"),
                )
            return "recovered"

        result = connection_limit_func()
        assert result == "recovered"
        assert call_count == 2

    def test_retry_callback_invoked(self):
        """Should call on_retry callback on each retry."""
        from app.database.retry import db_retry

        retry_calls = []

        @db_retry(max_retries=2, base_delay=0.01, on_retry=lambda e, n: retry_calls.append((str(e), n)))
        def flaky_func():
            if len(retry_calls) < 1:
                raise OperationalError(
                    "SSL SYSCALL error: EOF detected",
                    {},
                    Exception("connection lost"),
                )
            return "done"

        result = flaky_func()
        assert result == "done"
        assert len(retry_calls) == 1
        assert retry_calls[0][1] == 1  # attempt number


class TestGetDbDependency:
    """Tests for the get_db FastAPI dependency."""

    def test_get_db_yields_session(self):
        """Should yield a valid session."""
        gen = get_db()
        db = next(gen)
        assert db is not None
        try:
            next(gen)
        except StopIteration:
            pass

    def test_get_db_closes_session_on_success(self):
        """Should close session after successful use."""
        gen = get_db()
        db = next(gen)
        db_ref = db
        try:
            next(gen)
        except StopIteration:
            pass
        # Session should be closed - trying to use it should fail or be invalid
        assert db_ref.is_active is False or db_ref._flushed is False

    def test_get_db_rolls_back_on_error(self):
        """Should rollback uncommitted work when an exception occurs."""
        gen = get_db()
        db = next(gen)
        # Add a dirty object but don't commit
        from app.models.user import User
        from uuid import uuid4
        user = User(id=uuid4(), email="test@test.com", name="Test", role="user")
        db.add(user)
        assert db.dirty  # Should be dirty

        # Simulate an exception during request processing
        try:
            gen.throw(ValueError("simulated error"))
        except ValueError:
            pass

        # Session should have been rolled back and closed
        assert db.is_active is False or not db.dirty


class TestEngineConfiguration:
    """Tests for the database engine configuration."""

    def test_engine_has_pool_pre_ping(self):
        """Engine should have pool_pre_ping enabled."""
        assert engine.pool._pre_ping is True

    def test_engine_pool_settings(self):
        """Engine pool should have correct settings for Neon."""
        pool = engine.pool
        assert pool._pool_size == 5
        assert pool._max_overflow == 10
        assert pool._timeout == 30

    def test_sessionmaker_configuration(self):
        """SessionLocal should be configured correctly."""
        assert SessionLocal.kw["autocommit"] is False
        assert SessionLocal.kw["autoflush"] is False


class TestPoolStatusLogging:
    """Tests for pool status helper."""

    def test_pool_status_returns_dict(self):
        """Pool status should return a dict with expected keys."""
        from app.database.session import _pool_status
        status = _pool_status(engine)
        assert "size" in status
        assert "checked_in" in status
        assert "checked_out" in status
        assert "overflow" in status


class TestIsRetryableError:
    """Tests for the _is_retryable_error helper."""

    def test_ssl_eof_is_retryable(self):
        from app.database.retry import _is_retryable_error
        exc = OperationalError("SSL SYSCALL error: EOF detected", {}, Exception())
        assert _is_retryable_error(exc) is True

    def test_connection_closed_is_retryable(self):
        from app.database.retry import _is_retryable_error
        exc = OperationalError("server closed the connection unexpectedly", {}, Exception())
        assert _is_retryable_error(exc) is True

    def test_connection_limit_is_retryable(self):
        from app.database.retry import _is_retryable_error
        exc = OperationalError("remaining connection slots are reserved", {}, Exception())
        assert _is_retryable_error(exc) is True

    def test_integrity_error_not_retryable(self):
        from app.database.retry import _is_retryable_error
        from sqlalchemy.exc import IntegrityError
        exc = IntegrityError("duplicate key", {}, Exception())
        assert _is_retryable_error(exc) is False

    def test_programming_error_not_retryable(self):
        from app.database.retry import _is_retryable_error
        from sqlalchemy.exc import ProgrammingError
        exc = ProgrammingError("relation does not exist", {}, Exception())
        assert _is_retryable_error(exc) is False
