"""SchedulerService — centralised, asyncio-based job scheduler for the AI Office.

Architecture
------------
SchedulerService (singleton)
    ├── JobRegistry   — in-memory map of named jobs with metadata
    ├── Tick loop     — single asyncio task that wakes every N seconds
    ├── Overlap guard — prevents the same job from running twice simultaneously
    ├── Retry logic   — exponential back-off on failure, configurable max retries
    └── Lifecycle     — starts/stops with FastAPI lifespan, respects agent status

Why NOT APScheduler / Celery / Redis?
    * The project already runs everything in-process with asyncio — no broker
      infrastructure exists and adding one would be a significant operational
      change for a single-process FastAPI deployment.
    * APScheduler would work but adds a dependency that duplicates most of what
      a thin asyncio wrapper provides for this scale.
    * Celery/Redis require external services that are not in requirements.txt
      and are overkill for a development/small-team deployment.

Design goals
    * **Non-blocking** — all jobs are async; long-running work is handed off
      via ``asyncio.to_thread``.
    * **Overlap protection** — a job that is still running is skipped on the
      next tick (tracked via ``_running_jobs``).
    * **Deterministic scheduling** — each job declares an interval in seconds;
      the tick loop compares ``last_run + interval <= now``.
    * **Retry with back-off** — failed jobs are retried up to ``max_retries``
      times with exponential delay (base 2^attempt, capped).
    * **Agent lifecycle aware** — agent-related jobs are skipped when the
      owning agent is not ACTIVE.
    * **Structured logging** — every entry point logs with machine-readable
      ``extra`` dicts.
    * **Single-instance guarantee** — ``start()`` is a no-op if already running.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job metadata
# ---------------------------------------------------------------------------

@dataclass
class ScheduledJob:
    """Metadata for a single scheduled job."""
    name: str
    func: Callable[..., Awaitable[Any]]
    interval_seconds: int
    max_retries: int = 3
    retry_base_delay: float = 2.0       # seconds, multiplied by 2^attempt
    retry_cap: float = 120.0             # max back-off in seconds
    enabled: bool = True
    # Optional agent association — when set, the scheduler will check the
    # agent's lifecycle status before running and skip if not ACTIVE.
    agent_id: Optional[str] = None

    # Runtime state (managed by the scheduler, not the caller)
    last_run_at: float = 0.0             # monotonic timestamp
    last_success: bool = True
    consecutive_failures: int = 0
    next_retry_at: float = 0.0           # monotonic timestamp
    total_runs: int = 0
    total_failures: int = 0
    _running: bool = field(default=False, repr=False)


# ---------------------------------------------------------------------------
# Scheduler service
# ---------------------------------------------------------------------------

class SchedulerService:
    """Singleton asyncio-based job scheduler.

    Usage::

        scheduler = SchedulerService.get_instance()
        scheduler.register_job("gmail_monitor", gmail_func, interval_seconds=300)
        await scheduler.start()
        # ...
        await scheduler.stop()
    """

    _instance: Optional["SchedulerService"] = None

    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._tick_task: Optional[asyncio.Task] = None
        self._tick_interval: int = 5  # seconds between scheduler ticks
        self._logger = logging.getLogger("scheduler")

    @classmethod
    def get_instance(cls) -> "SchedulerService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scheduler tick loop. No-op if already running."""
        if self._running:
            self._logger.warning("Scheduler already running — ignoring duplicate start")
            return

        self._running = True
        self._tick_task = asyncio.create_task(self._tick_loop())
        self._logger.info(
            "Scheduler started",
            extra={"job_count": len(self._jobs), "tick_interval": self._tick_interval},
        )

    async def stop(self) -> None:
        """Stop the scheduler and wait for in-flight jobs to finish."""
        if not self._running:
            return

        self._running = False
        self._logger.info("Scheduler stopping")

        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

        # Wait briefly for any jobs that were mid-flight
        running = [j for j in self._jobs.values() if j._running]
        if running:
            self._logger.info(f"Waiting for {len(running)} in-flight jobs to complete")
            # Give them up to 10 seconds; they should respect cancellation
            await asyncio.sleep(min(10, len(running) * 2))

        # Clear registrations so a later startup in the same process (tests
        # boot the lifespan repeatedly) can re-register the same job names.
        self._jobs.clear()

        self._logger.info("Scheduler stopped")

    # ------------------------------------------------------------------
    # Job registration
    # ------------------------------------------------------------------

    def register_job(
        self,
        name: str,
        func: Callable[..., Awaitable[Any]],
        interval_seconds: int,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_cap: float = 120.0,
        enabled: bool = True,
        agent_id: Optional[str] = None,
    ) -> None:
        """Register a job. Raises if a job with the same name exists."""
        if name in self._jobs:
            raise ValueError(f"Job '{name}' already registered")

        job = ScheduledJob(
            name=name,
            func=func,
            interval_seconds=max(1, interval_seconds),
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            retry_cap=retry_cap,
            enabled=enabled,
            agent_id=agent_id,
        )
        self._jobs[name] = job
        self._logger.info(
            "Job registered",
            extra={"job_name": name, "interval": interval_seconds, "agent_id": agent_id},
        )

    def unregister_job(self, name: str) -> bool:
        """Remove a job by name. Returns False if not found."""
        if name not in self._jobs:
            return False
        del self._jobs[name]
        self._logger.info("Job unregistered", extra={"job_name": name})
        return True

    def enable_job(self, name: str) -> bool:
        job = self._jobs.get(name)
        if not job:
            return False
        job.enabled = True
        self._logger.info("Job enabled", extra={"job_name": name})
        return True

    def disable_job(self, name: str) -> bool:
        job = self._jobs.get(name)
        if not job:
            return False
        job.enabled = False
        self._logger.info("Job disabled", extra={"job_name": name})
        return True

    def get_job(self, name: str) -> Optional[ScheduledJob]:
        return self._jobs.get(name)

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------

    async def _tick_loop(self) -> None:
        """Main scheduler loop. Runs every ``_tick_interval`` seconds."""
        self._logger.info("Scheduler tick loop entered")
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(
                    "Unhandled error in scheduler tick",
                    extra={"error": str(e)},
                    exc_info=True,
                )
            await asyncio.sleep(self._tick_interval)
        self._logger.info("Scheduler tick loop exited")

    async def _tick(self) -> None:
        """Single tick: evaluate all registered jobs and fire those that are due."""
        now = time.monotonic()
        for job in self._jobs.values():
            if not job.enabled:
                continue

            # Overlap guard — skip if still running
            if job._running:
                self._logger.debug("Job still running, skipping", extra={"job_name": job.name})
                continue

            # Retry back-off — skip if not yet time to retry
            if job.consecutive_failures > 0 and now < job.next_retry_at:
                continue

            # Interval check
            elapsed = now - job.last_run_at
            if elapsed < job.interval_seconds and job.last_run_at > 0:
                continue

            # Agent lifecycle check
            if job.agent_id:
                if not await self._check_agent_active(job.agent_id):
                    self._logger.debug(
                        "Skipping job — agent not active",
                        extra={"job_name": job.name, "agent_id": job.agent_id},
                    )
                    continue

            # Fire the job
            asyncio.create_task(self._run_job(job))

    # ------------------------------------------------------------------
    # Job execution
    # ------------------------------------------------------------------

    async def _run_job(self, job: ScheduledJob) -> None:
        """Execute a single job with overlap protection and retry logic."""
        job._running = True
        job.last_run_at = time.monotonic()
        job.total_runs += 1

        self._logger.info(
            "Job started",
            extra={"job_name": job.name, "run_number": job.total_runs, "agent_id": job.agent_id},
        )

        try:
            await job.func()
            # Success
            job.last_success = True
            job.consecutive_failures = 0
            job.next_retry_at = 0
            self._logger.info("Job completed successfully", extra={"job_name": job.name})

        except asyncio.CancelledError:
            job.last_success = False
            self._logger.info("Job cancelled", extra={"job_name": job.name})
            raise  # propagate so the task is marked cancelled

        except Exception as e:
            job.last_success = False
            job.consecutive_failures += 1
            job.total_failures += 1

            # Calculate retry delay with exponential back-off
            attempt = min(job.consecutive_failures, 10)
            delay = min(job.retry_base_delay ** attempt, job.retry_cap)
            job.next_retry_at = time.monotonic() + delay

            if job.consecutive_failures <= job.max_retries:
                self._logger.warning(
                    "Job failed — will retry",
                    extra={
                        "job_name": job.name,
                        "error": str(e),
                        "attempt": job.consecutive_failures,
                        "max_retries": job.max_retries,
                        "retry_in_seconds": round(delay, 1),
                    },
                )
            else:
                self._logger.error(
                    "Job failed — max retries exceeded, disabling",
                    extra={
                        "job_name": job.name,
                        "error": str(e),
                        "total_failures": job.total_failures,
                    },
                    exc_info=True,
                )
                job.enabled = False

        finally:
            job._running = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _check_agent_active(self, agent_id: str) -> bool:
        """Check if the given agent is in ACTIVE lifecycle state."""
        try:
            from app.database.session import SessionLocal
            from app.models.agent import AIAgent, LifecycleStatus

            db = SessionLocal()
            try:
                agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
                return agent is not None and agent.lifecycle_status == LifecycleStatus.ACTIVE
            finally:
                db.close()
        except Exception as e:
            self._logger.error(
                "Failed to check agent status",
                extra={"agent_id": agent_id, "error": str(e)},
            )
            return False  # fail-closed: skip the job if we can't verify

    # ------------------------------------------------------------------
    # Status / monitoring
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return scheduler status for API exposure."""
        return {
            "running": self._running,
            "tick_interval": self._tick_interval,
            "job_count": len(self._jobs),
            "jobs": {
                name: {
                    "enabled": job.enabled,
                    "interval_seconds": job.interval_seconds,
                    "agent_id": job.agent_id,
                    "last_run_at": job.last_run_at,
                    "consecutive_failures": job.consecutive_failures,
                    "total_runs": job.total_runs,
                    "total_failures": job.total_failures,
                    "currently_running": job._running,
                }
                for name, job in self._jobs.items()
            },
        }


# Global singleton
scheduler = SchedulerService.get_instance()
