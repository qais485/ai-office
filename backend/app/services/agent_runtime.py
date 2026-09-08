"""Agent Runtime — manages autonomous execution loops for active agents.

Architecture:
    AgentRuntime (singleton)
        ├── AgentLoop per active agent
        │     ├── Polls TriggerService for pending triggers
        │     ├── LLM Reasoning (decide what to do)
        │     ├── Tool Selection (pick allowed tool)
        │     └── ToolExecutionService (execute + approve)
        ├── ScheduledTriggerWorker (checks cron-like triggers)
        └── Lifecycle integration (start/stop on status changes)

Key principles:
    - No execution without a valid persisted trigger
    - Each execution gets a unique execution_id for tracing
    - Prevent duplicate runtimes per agent
    - Separate lifecycle state from execution state
    - Non-blocking async execution
    - Structured logging throughout
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List
from uuid import UUID

logger = logging.getLogger(__name__)

# Inbound Telegram event types (MTProto account + Bot API) — the runtime
# treats both identically: bot-sender skip, chat pinning, reply guard tag.
_TELEGRAM_EVENT_TYPES = ("telegram_message_received", "telegram_bot_message_received")


class AgentLoop:
    """Execution loop for a single agent. Polls for pending triggers and processes them."""

    def __init__(self, agent_id: str, runtime: "AgentRuntime"):
        self.agent_id = agent_id
        self.runtime = runtime
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_trigger_id: Optional[str] = None
        self._current_execution_id: Optional[str] = None
        self._logger = logging.getLogger(f"agent_runtime.loop.{agent_id[:8]}")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_trigger_id(self) -> Optional[str]:
        return self._current_trigger_id

    @property
    def current_execution_id(self) -> Optional[str]:
        return self._current_execution_id

    async def start(self) -> None:
        """Start the agent loop."""
        if self._running:
            self._logger.warning("Agent loop already running, ignoring start")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self._logger.info("Agent loop started", extra={"agent_id": self.agent_id})

    async def stop(self) -> None:
        """Stop the agent loop gracefully."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._logger.info("Agent loop stopped", extra={"agent_id": self.agent_id})

    async def _run_loop(self) -> None:
        """Main loop: poll for pending triggers and process them."""
        self._logger.info("Agent loop entering main loop")
        while self._running:
            try:
                await self._poll_and_process()
                # 5s poll: each iteration costs a DB checkout (pre-ping) plus a
                # query against a remote DB. With several agents this hum was a
                # constant share of the 15-connection pool; 5s keeps trigger
                # latency acceptable while cutting background load by 60%.
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(
                    "Unexpected error in agent loop",
                    extra={"agent_id": self.agent_id, "error": str(e)},
                    exc_info=True,
                )
                await asyncio.sleep(5)
        self._logger.info("Agent loop exited main loop")

    async def _poll_and_process(self) -> None:
        """Poll for pending triggers and process the first one found."""
        try:
            from app.database.session import SessionLocal
            from app.models.agent_trigger import AgentTrigger, TriggerStatus
            from app.services.trigger_service import TriggerService

            db = SessionLocal()
            try:
                trigger = db.query(AgentTrigger).filter(
                    AgentTrigger.agent_id == UUID(self.agent_id),
                    AgentTrigger.status == TriggerStatus.PENDING,
                    AgentTrigger.is_active == True,
                ).order_by(AgentTrigger.created_at.asc()).first()

                if not trigger:
                    return

                self._current_trigger_id = str(trigger.id)

                trigger_service = TriggerService(db)
                execution = trigger_service.start_execution(trigger)
                self._current_execution_id = str(execution.id)

                await self._process_trigger(db, trigger, execution, trigger_service)

                self._current_trigger_id = None
                self._current_execution_id = None

            finally:
                db.close()

        except Exception as e:
            self._logger.error(
                "Error polling/processing triggers",
                extra={"agent_id": self.agent_id, "error": str(e)},
                exc_info=True,
            )

    async def _process_trigger(self, db, trigger, execution, trigger_service) -> None:
        """Process a single trigger through the full pipeline."""
        self._logger.info(
            "Processing trigger",
            extra={
                "trigger_id": str(trigger.id),
                "execution_id": str(execution.id),
                "trigger_type": trigger.trigger_type.value,
                "agent_id": self.agent_id,
            },
        )

        try:
            from app.models.agent import AIAgent, LifecycleStatus
            agent = db.query(AIAgent).filter(AIAgent.id == UUID(self.agent_id)).first()

            if not agent:
                trigger_service.complete_execution(execution, trigger, success=False, error_message="Agent not found")
                return

            if agent.lifecycle_status != LifecycleStatus.ACTIVE:
                trigger_service.complete_execution(
                    execution, trigger, success=False,
                    error_message=f"Agent not active (status: {agent.lifecycle_status.value})",
                )
                return

            # Create a real Task row for this execution so the dashboard
            # Tasks/Performance tabs reflect actual agent work.
            task = self._create_execution_task(db, agent, trigger)
            trigger_service.update_execution(execution, status=ExecutionStatus.REASONING)

            result = await self._reason_and_act(db, agent, trigger, execution, trigger_service, task)

            if result.get("success"):
                trigger_service.complete_execution(execution, trigger, success=True, result=result)
                self._log_room_activity(
                    db, agent, trigger, execution, "task_completed", "success", result
                )
                self._finish_execution_task(db, task, success=True, result=result)
            else:
                trigger_service.complete_execution(
                    execution, trigger, success=False,
                    error_message=result.get("error", "Unknown error"),
                )
                self._log_room_activity(
                    db, agent, trigger, execution, "task_failed", "failed", result
                )
                self._finish_execution_task(db, task, success=False, result=result)

        except Exception as e:
            self._logger.error(
                "Error processing trigger",
                extra={"trigger_id": str(trigger.id), "execution_id": str(execution.id), "error": str(e)},
                exc_info=True,
            )
            trigger_service.complete_execution(execution, trigger, success=False, error_message=str(e))

    # ------------------------------------------------------------------
    # Task lifecycle for dashboard (Tasks/Performance tabs)
    # ------------------------------------------------------------------

    def _describe_trigger(self, trigger) -> str:
        """Short human title for the work item this trigger represents."""
        payload = trigger.payload or {}
        ttype = trigger.trigger_type.value
        if ttype == "integration" and payload.get("subject"):
            return f"Handle email: {payload.get('subject', '')[:80]}"
        if payload.get("instruction"):
            return str(payload["instruction"])[:100]
        return f"Process {ttype} trigger"

    def _create_execution_task(self, db, agent, trigger):
        """Create a PENDING→RUNNING task for this trigger execution.

        Best-effort: a failure here must never break the trigger pipeline.
        Returns the Task row or None.
        """
        try:
            from datetime import datetime, timezone

            from app.models.task import Task, TaskStatus, TaskPriority
            from app.services.task_service import TaskService
            from app.events.publisher import publish_task_event
            from app.events.types import EventType

            task = Task(
                title=self._describe_trigger(trigger)[:200],
                description=f"Auto-created from {trigger.trigger_type.value} trigger",
                agent_id=agent.id,
                task_type="general",
                priority=TaskPriority.MEDIUM,
                status=TaskStatus.RUNNING,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(task)
            db.commit()
            db.refresh(task)

            self._fire_async(publish_task_event(
                event_type=EventType.TASK_CREATED,
                task_id=task.id,
                agent_id=task.agent_id,
                title=task.title,
                status=task.status.value,
                is_execution_bookkeeping=True,
            ))
            return task
        except Exception as e:
            self._logger.warning("Failed to create execution task: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    def _finish_execution_task(self, db, task, success: bool, result: Dict[str, Any]) -> None:
        """Complete or fail the execution task. Best-effort."""
        if task is None:
            return
        try:
            from datetime import datetime, timezone

            from app.models.task import TaskStatus
            from app.events.publisher import publish_task_event
            from app.events.types import EventType

            # Stale-check: another flow (approval wait) may own the task now.
            fresh = db.query(type(task)).filter(type(task).id == task.id).first()
            if fresh is None or fresh.status != TaskStatus.RUNNING:
                return

            fresh.completed_at = datetime.now(timezone.utc).isoformat()
            if success:
                fresh.status = TaskStatus.COMPLETED
                fresh.result = str(result.get("message") or result.get("data") or "Done")[:500]
            else:
                fresh.status = TaskStatus.FAILED
                fresh.error_message = str(result.get("error") or "Unknown error")[:500]
            db.commit()
            db.refresh(fresh)

            event_type = EventType.TASK_COMPLETED if success else EventType.TASK_FAILED
            self._fire_async(publish_task_event(
                event_type=event_type,
                task_id=fresh.id,
                agent_id=fresh.agent_id,
                title=fresh.title,
                status=fresh.status.value,
            ))
        except Exception as e:
            self._logger.warning("Failed to finish execution task: %s", e)
            try:
                db.rollback()
            except Exception:
                pass

    def _fire_async(self, coro) -> None:
        """Fire-and-forget an async event publish from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            try:
                asyncio.run(coro)
            except Exception:
                pass
        except Exception:
            pass

    def _mark_task_waiting_approval(self, db, task, approval_id) -> None:
        """Put the execution task into WAITING_APPROVAL until the CEO decides.
        Best-effort."""
        if task is None or not approval_id:
            return
        try:
            from uuid import UUID as _UUID

            from app.models.task import Task, TaskStatus

            fresh = db.query(Task).filter(Task.id == task.id).first()
            if fresh is None or fresh.status != TaskStatus.RUNNING:
                return
            fresh.status = TaskStatus.WAITING_APPROVAL
            fresh.approval_id = _UUID(str(approval_id))
            db.commit()
        except Exception as e:
            self._logger.warning("Failed to mark task waiting_approval: %s", e)
            try:
                db.rollback()
            except Exception:
                pass

    def _log_room_activity(self, db, agent, trigger, execution, activity_type: str, status: str, result: Dict[str, Any]) -> None:
        """Record an AgentActivity row so the room dashboard/timeline shows
        what the agent actually did. Best-effort: logging must never break
        the trigger pipeline."""
        try:
            from app.services.activity_service import ActivityService

            payload = trigger.payload or {}
            trigger_type = trigger.trigger_type.value

            # Human-readable context depending on trigger type
            if trigger_type == "integration" and payload.get("subject"):
                context = f"email from {payload.get('from_address', 'unknown')} — '{payload.get('subject')}'"
            elif trigger_type == "integration" and payload.get("message_id") and payload.get("chat_id"):
                context = f"Telegram message from {payload.get('from_address', 'unknown')} in '{payload.get('chat_title', 'chat')}'"
            elif payload.get("instruction"):
                context = f"instruction: {payload['instruction']}"
            else:
                context = f"{trigger_type} trigger"

            action = getattr(execution, "selected_action", None)
            tool = getattr(execution, "selected_tool", None)
            reason = getattr(execution, "llm_reasoning", None) or ""

            if status == "failed":
                description = f"Failed processing {context}: {(result or {}).get('error', 'unknown error')}"
            elif (result or {}).get("requires_approval"):
                description = f"Reply drafted for {context} — held for CEO approval before sending"
            elif action and action != "null":
                description = f"Responded to {context} — executed '{action}'" + (f" via {tool}" if tool else "")
            else:
                description = f"Reviewed {context} — no action needed"

            ActivityService(db).log_agent_action(
                agent_id=UUID(self.agent_id),
                activity_type=activity_type,
                description=description[:280],
                tool_name=tool,
                status=status,
                metadata={"trigger_id": str(trigger.id), "reason": reason[:200]},
            )
        except Exception as e:
            self._logger.warning("Failed to log room activity: %s", e)

    # Senders that never need an LLM decision (pure automated traffic).
    _AUTOMATED_SENDER_RE = re.compile(
        r"(?i)^(no-?reply|donotreply|do-?not-?reply|notifications?|alerts?|noreply"
        r"|newsletter|marketing|billing|invoices?|updates?|mailer-daemon|postmaster"
        r"|bounce|[a-z0-9._%+-]+@(noreply\.[a-z0-9.-]+|notifications\.google\.com"
        r"|facebookmail\.com|linkedin\.com|twitter\.com|x\.com))"
    )

    @classmethod
    def _is_automated_sender(cls, from_address: str) -> bool:
        """Heuristic: does this sender look like an automated system?"""
        addr = (from_address or "").strip()
        if not addr:
            return False
        if cls._AUTOMATED_SENDER_RE.match(addr):
            return True
        local = addr.split("@")[0].lower()
        return local in {"noreply", "no-reply", "donotreply", "do-not-reply", "notifications", "alerts"}

    async def _reason_and_act(self, db, agent, trigger, execution, trigger_service, task=None) -> Dict[str, Any]:
        """Use LLM to reason about the trigger and decide what action to take."""
        from app.core.llm import get_llm
        from app.core.config import settings
        from app.services.tool_execution_service import ToolExecutionService
        from app.models.trigger_execution import ExecutionStatus

        goals = agent.goals.split("|") if agent.goals else []
        rules = agent.rules.split("|") if agent.rules else []
        tools = agent.tools.split("|") if agent.tools else []

        # ── Token-saving guards (before ANY LLM call) ────────────────────
        # 1) An agent with no tools can never act — skip the LLM entirely.
        if not [t for t in tools if t]:
            trigger_service.update_execution(
                execution,
                llm_reasoning="Skipped: agent has no tools assigned",
                selected_action=None,
            )
            return {"success": True, "message": "Agent has no tools; no reasoning needed"}

        # 2) Pure automated senders (noreply/notifications/...) never need a
        #    decision — save the whole call instead of paying for a null action.
        #    Telegram: bot senders are always skipped (no bot-to-bot loops).
        payload = trigger.payload or {}
        if (
            trigger.trigger_type.value == "integration"
            and (
                (
                    trigger.source_event_type == "email_received"
                    and settings.LLM_SKIP_AUTOMATED_SENDERS
                )
                or trigger.source_event_type in _TELEGRAM_EVENT_TYPES
            )
        ):
            from_addr = payload.get("from_address", "")
            if trigger.source_event_type == "email_received":
                if settings.LLM_SKIP_AUTOMATED_SENDERS and self._is_automated_sender(from_addr):
                    trigger_service.update_execution(
                        execution,
                        llm_reasoning=f"Skipped: automated sender ({from_addr})",
                        selected_action=None,
                    )
                    return {
                        "success": True,
                        "message": f"Automated email from {from_addr}; no reasoning needed",
                    }
            elif payload.get("is_bot"):
                trigger_service.update_execution(
                    execution,
                    llm_reasoning=f"Skipped: bot sender ({from_addr})",
                    selected_action=None,
                )
                return {
                    "success": True,
                    "message": f"Bot message from {from_addr}; no reasoning needed",
                }

        prompt = self._build_reasoning_prompt(agent, trigger, goals, rules, tools)

        try:
            llm = get_llm()
            response = await asyncio.to_thread(lambda: llm.invoke(prompt))
            decision = self._parse_llm_response(response.content)

            trigger_service.update_execution(
                execution,
                llm_reasoning=decision.get("reason", ""),
                selected_tool=decision.get("tool"),
                selected_action=decision.get("action"),
                tool_parameters=decision.get("parameters", {}),
            )

            if not decision.get("action"):
                return {"success": True, "message": "No action needed based on reasoning"}

            tool_name = decision.get("tool")
            action_name = decision.get("action")
            parameters = decision.get("parameters", {}) or {}

            # Anti-duplicate: tag outgoing replies with the source message id
            # (Gmail msg id / IMAP uid) so ToolExecutionService's reply guard
            # can block a second send for the same email.
            if action_name == "send_email":
                source_id = (
                    payload.get("email_id")
                    or payload.get("message_id")
                    or trigger.source_event_id
                )
                if source_id:
                    parameters["_reply_to_message_id"] = str(source_id)

            # Telegram replies: pin the reply to the source chat and tag the
            # source message so the reply guard can block duplicate sends.
            # Account replies: tg:<chat>:<msg>; Bot replies: tgbot:<chat>:<msg>
            # (separate guard namespaces per channel).
            elif (
                action_name == "send_message"
                and trigger.source_event_type in _TELEGRAM_EVENT_TYPES
            ):
                chat_id = str(payload.get("chat_id") or "").strip()
                if chat_id:
                    parameters["chat_id"] = chat_id
                    source_id = payload.get("message_id") or trigger.source_event_id
                    if source_id:
                        prefix = (
                            "tgbot"
                            if trigger.source_event_type == "telegram_bot_message_received"
                            else "tg"
                        )
                        parameters["_reply_to_message_id"] = f"{prefix}:{chat_id}:{source_id}"

            if tool_name and tool_name not in tools:
                return {"success": False, "error": f"Tool '{tool_name}' not assigned to agent"}

            if tool_name and action_name:
                trigger_service.update_execution(execution, status=ExecutionStatus.EXECUTING)

                # Email/Telegram replies classified as AUTOMATED must get CEO
                # approval before actually sending (per CEO policy).
                force_approval = (
                    trigger.trigger_type.value == "integration"
                    and (
                        trigger.source_event_type == "email_received"
                        or trigger.source_event_type in _TELEGRAM_EVENT_TYPES
                    )
                    and str(decision.get("email_class", "")).upper() == "AUTOMATED"
                )

                execution_service = ToolExecutionService(db)

                # Run tool execution off the event loop — provider calls
                # (Gmail API etc.) block otherwise and freeze all HTTP traffic.
                result = await asyncio.to_thread(
                    lambda: execution_service.execute_tool(
                        agent_id=UUID(self.agent_id),
                        tool_name=tool_name,
                        action=action_name,
                        parameters=parameters,
                        reason=decision.get("reason", f"Triggered by {trigger.trigger_type.value}"),
                        force_approval=force_approval,
                    )
                )
                if force_approval and result.get("requires_approval"):
                    self._mark_task_waiting_approval(db, task, result.get("approval_id"))
                    channel = (
                        "Telegram"
                        if trigger.source_event_type in _TELEGRAM_EVENT_TYPES
                        else "email"
                    )
                    return {
                        "success": True,
                        "message": f"Reply drafted but held for CEO approval (AUTOMATED {channel} message)",
                        "approval_id": result.get("approval_id"),
                        "requires_approval": True,
                    }
                return result

            return {"success": True, "message": "Reasoning complete, no tool execution needed"}

        except Exception as e:
            self._logger.error(
                "LLM reasoning failed",
                extra={"agent_id": self.agent_id, "error": str(e)},
                exc_info=True,
            )
            return {"success": False, "error": f"LLM reasoning failed: {str(e)}"}

    def _build_reasoning_prompt(self, agent, trigger, goals: List[str], rules: List[str], tools: List[str]) -> str:
        """Build a prompt for the LLM to reason about the trigger."""
        trigger_context = ""

        payload = trigger.payload or {}

        if trigger.trigger_type.value == "integration":
            integration_name = trigger.match_integration or "unknown"
            event_type = trigger.source_event_type or "unknown"

            # Format email content readably for email events.
            # Token saving: hard-cap the body text we send to the LLM.
            if event_type == "email_received" and "subject" in payload:
                from_addr = payload.get("from_address", "unknown")
                subject = payload.get("subject", "(no subject)")
                body = payload.get("body_preview", payload.get("snippet", ""))

                from app.core.config import settings as _settings
                max_body = _settings.LLM_EMAIL_BODY_MAX_CHARS
                if len(body) > max_body:
                    body = body[:max_body] + "...[truncated]"

                trigger_context = f"""Email received.

From: {from_addr}
Subject: {subject}

Body:
{body}

Reply with JSON only. For email events always include "email_class" (HUMAN = written by a real person, AUTOMATED = system/newsletter/noreply). If AUTOMATED, still send a brief reply via send_email; the platform automatically holds AUTOMATED replies for CEO approval."""
            elif event_type in _TELEGRAM_EVENT_TYPES and "message_id" in payload:
                is_bot_channel = event_type == "telegram_bot_message_received"
                reply_tool = (
                    "telegram_messaging" if is_bot_channel else "telegram_account_messaging"
                )
                from_addr = payload.get("from_address", "unknown")
                chat_title = payload.get("chat_title", "Private chat")
                body = payload.get("text", "")

                from app.core.config import settings as _settings
                max_body = _settings.LLM_EMAIL_BODY_MAX_CHARS
                if len(body) > max_body:
                    body = body[:max_body] + "...[truncated]"

                channel = "Telegram Bot chat" if is_bot_channel else "Telegram"
                trigger_context = f"""Customer message received via {channel}.

From: {from_addr}
Chat: {chat_title} (chat_id: {payload.get('chat_id', '')})
Message ID: {payload.get('message_id')}

Text:
{body}

Reply with JSON only. For these messages always include "email_class" (HUMAN = a real customer, AUTOMATED = bot/system message). To reply, use action="send_message", tool="{reply_tool}" and echo the SAME chat_id in parameters. Answer from your knowledge when you can. If AUTOMATED, still draft a brief reply; the platform automatically holds AUTOMATED replies for CEO approval."""
            else:
                trigger_context = f"""Integration event received:
Integration: {integration_name}
Event type: {event_type}
Event ID: {trigger.source_event_id or 'unknown'}
Payload: {payload}
"""
        elif trigger.trigger_type.value == "room":
            trigger_context = f"""Room event received:
Room ID: {trigger.match_room_id or 'unknown'}
Event type: {trigger.source_event_type or 'unknown'}
Payload: {payload}
"""
        elif trigger.trigger_type.value == "scheduled":
            trigger_context = f"""Scheduled execution triggered.
This is a periodic run. Check if any action is needed.
"""
        elif trigger.trigger_type.value == "manual":
            trigger_context = f"Manual trigger: {payload.get('instruction', 'No instruction')}"

        # One-line tool hint — full JSON schema examples removed to save tokens
        tool_hints = ""
        if "telegram_account_messaging" in tools:
            tool_hints = 'To reply on Telegram: action="send_message", tool="telegram_account_messaging", parameters={chat_id, text}.'
        elif "telegram_messaging" in tools:
            tool_hints = 'To reply on Telegram via the bot: action="send_message", tool="telegram_messaging", parameters={chat_id, text}.'
        elif "email_writer" in tools or "email_reader" in tools:
            tool_hints = 'To reply by email: action="send_email", tool="email_writer", parameters={to, subject, body}.'
        elif "gmail" in [t.lower() for t in tools]:
            tool_hints = 'To reply by email: action="send_email", tool="gmail", parameters={to, subject, body}.'

        # Token saving: compact persona + single-line goals/rules instead of
        # multi-line lists — this prompt is sent on EVERY trigger execution.
        persona = f'Agent "{agent.name}" (role: {agent.role}).'
        goal_line = "; ".join(g.strip() for g in goals if g and g.strip())
        rule_line = "; ".join(r.strip() for r in rules if r and r.strip())

        return f"""{persona} Tools: {', '.join(t for t in tools if t)}.
{f'Goals: {goal_line}.' if goal_line else ''}
{f'Rules: {rule_line}.' if rule_line else ''}

{trigger_context}
{tool_hints}
Respond with JSON only (no markdown):
{{"action": "action_name or null", "tool": "tool_name or null", "parameters": {{}}, "reason": "one short sentence", "email_class": "HUMAN or AUTOMATED (email events only)"}}

Use only your listed tools. If no action is needed, set action to null and keep the reason to a few words."""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM's JSON response."""
        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except (json.JSONDecodeError, IndexError):
            self._logger.warning("Failed to parse LLM response as JSON", extra={"response": response[:200]})
            return {"action": None, "tool": None, "parameters": {}, "reason": "Failed to parse LLM response"}


class AgentRuntime:
    """Singleton runtime manager for all agent loops.

    Usage:
        runtime = AgentRuntime.get_instance()
        await runtime.start()
        # ...
        await runtime.stop()
    """

    _instance: Optional["AgentRuntime"] = None

    def __init__(self):
        self._loops: Dict[str, AgentLoop] = {}
        self._running = False
        self._startup_task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger("agent_runtime")

    @classmethod
    def get_instance(cls) -> "AgentRuntime":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_running(self) -> bool:
        return self._running

    def get_loop(self, agent_id: str) -> Optional[AgentLoop]:
        return self._loops.get(agent_id)

    def get_all_loops(self) -> Dict[str, AgentLoop]:
        return dict(self._loops)

    async def start(self) -> None:
        """Start the runtime and activate all existing active agents."""
        if self._running:
            self._logger.warning("Runtime already running")
            return

        self._running = True
        self._logger.info("Agent runtime starting")

        # Register the scheduled trigger check as a scheduler job
        from app.services.scheduler import scheduler
        from app.core.config import settings

        # Remove old job if re-starting
        scheduler.unregister_job("agent_scheduled_triggers")

        scheduler.register_job(
            name="agent_scheduled_triggers",
            func=self._check_scheduled_triggers,
            interval_seconds=settings.AGENT_TRIGGER_WORKER_INTERVAL,
        )

        self._startup_task = asyncio.create_task(self._activate_existing_agents())
        self._logger.info("Agent runtime started")

    async def stop(self) -> None:
        """Stop all agent loops and the runtime."""
        if not self._running:
            return

        self._running = False
        self._logger.info("Agent runtime stopping")

        # Unregister the scheduled trigger job from the scheduler
        from app.services.scheduler import scheduler
        scheduler.unregister_job("agent_scheduled_triggers")

        if self._startup_task:
            self._startup_task.cancel()
            try:
                await self._startup_task
            except asyncio.CancelledError:
                pass

        stop_tasks = [loop.stop() for loop in self._loops.values()]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._loops.clear()
        self._logger.info("Agent runtime stopped")

    async def activate_agent(self, agent_id: str) -> bool:
        """Start an agent loop if not already running."""
        if agent_id in self._loops and self._loops[agent_id].is_running:
            self._logger.debug("Agent loop already running", extra={"agent_id": agent_id})
            return False

        loop = AgentLoop(agent_id, self)
        self._loops[agent_id] = loop
        await loop.start()
        self._logger.info("Agent activated in runtime", extra={"agent_id": agent_id})
        return True

    async def deactivate_agent(self, agent_id: str) -> bool:
        """Stop an agent loop."""
        loop = self._loops.get(agent_id)
        if not loop or not loop.is_running:
            self._logger.debug("Agent loop not running", extra={"agent_id": agent_id})
            return False

        await loop.stop()
        del self._loops[agent_id]
        self._logger.info("Agent deactivated in runtime", extra={"agent_id": agent_id})
        return True

    async def _activate_existing_agents(self) -> None:
        """On startup, find all active agents and start their loops."""
        try:
            from app.database.session import SessionLocal
            from app.models.agent import AIAgent, LifecycleStatus
            from app.models.agent_trigger import AgentTrigger, TriggerStatus

            db = SessionLocal()
            try:
                # Re-queue triggers stuck in 'processing' from a previous run.
                # At startup no loop is executing anything, so every trigger in
                # 'processing' state is an orphan from an interrupted process.
                # Without this they would never be picked up again (the poll
                # loop only takes PENDING triggers).
                stale = db.query(AgentTrigger).filter(
                    AgentTrigger.status == TriggerStatus.PROCESSING,
                ).all()
                if stale:
                    for t in stale:
                        t.status = TriggerStatus.PENDING
                    db.commit()
                    self._logger.warning(
                        f"Re-queued {len(stale)} orphaned 'processing' triggers back to pending"
                    )

                active_agents = db.query(AIAgent).filter(
                    AIAgent.lifecycle_status == LifecycleStatus.ACTIVE
                ).all()

                self._logger.info(f"Found {len(active_agents)} active agents to activate")

                for agent in active_agents:
                    agent_id = str(agent.id)
                    if agent_id not in self._loops:
                        loop = AgentLoop(agent_id, self)
                        self._loops[agent_id] = loop
                        await loop.start()
                        self._logger.info(
                            "Existing agent activated on startup",
                            extra={"agent_id": agent_id, "agent_name": agent.name},
                        )
            finally:
                db.close()

        except Exception as e:
            self._logger.error(
                "Failed to activate existing agents",
                extra={"error": str(e)},
                exc_info=True,
            )

    async def _check_scheduled_triggers(self) -> None:
        """Check for scheduled triggers that are due and fire them.

        This is registered as a scheduler job and called periodically.
        """
        try:
            from app.database.session import SessionLocal
            from app.services.trigger_service import TriggerService

            db = SessionLocal()
            try:
                trigger_service = TriggerService(db)
                due_triggers = trigger_service.get_due_scheduled_triggers()

                for trigger in due_triggers:
                    agent_id = str(trigger.agent_id)

                    if agent_id not in self._loops or not self._loops[agent_id].is_running:
                        continue

                    trigger.status = TriggerStatus.PROCESSING
                    db.commit()

                    execution = trigger_service.start_execution(trigger)

                    loop = self._loops[agent_id]
                    loop._current_trigger_id = str(trigger.id)
                    loop._current_execution_id = str(execution.id)

                    self._logger.info(
                        "Scheduled trigger fired",
                        extra={"trigger_id": str(trigger.id), "agent_id": agent_id},
                    )

                    await loop._process_trigger(db, trigger, execution, trigger_service)

                    loop._current_trigger_id = None
                    loop._current_execution_id = None

            finally:
                db.close()

        except Exception as e:
            self._logger.error(
                "Error checking scheduled triggers",
                extra={"error": str(e)},
                exc_info=True,
            )

    def get_status(self) -> Dict[str, Any]:
        """Get runtime status for monitoring."""
        return {
            "running": self._running,
            "active_loops": len(self._loops),
            "agents": {
                agent_id: {
                    "running": loop.is_running,
                    "current_trigger_id": loop.current_trigger_id,
                    "current_execution_id": loop.current_execution_id,
                }
                for agent_id, loop in self._loops.items()
            },
        }


# Re-export for backward compatibility
from app.models.agent_trigger import TriggerType, TriggerStatus  # noqa: E402, F401
from app.models.trigger_execution import ExecutionStatus  # noqa: E402, F401

# Global singleton
agent_runtime = AgentRuntime.get_instance()
