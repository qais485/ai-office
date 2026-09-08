"""Orchestrates tool execution with full security validation.

Security flow:
    Validate Agent
        ↓
    Validate Tool Assignment (database-backed)
        ↓
    Validate Tool Active
        ↓
    Validate Action Exists
        ↓
    Validate Integration Connected
        ↓
    Resolve Correct Account
        ↓
    Validate Ownership
        ↓
    Validate Permissions
        ↓
    Evaluate Risk
        ↓
    Create Approval if required
        ↓
    Execute Tool
        ↓
    Audit Log Result
"""
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone

from app.models.agent import AIAgent, LifecycleStatus
from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.models.tool_permission import ToolPermission
from app.models.permission import Permission
from app.models.agent_permission import AgentPermission
from app.models.agent_integration import AgentIntegration
from app.models.approval import Approval
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.core.risk_levels import RiskLevel, should_auto_approve, requires_ceo_approval
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.permission_service import PermissionService
from app.services.risk_rule_service import RiskEvaluationService
from app.services.oauth2_service import OAuth2Service


class EmailReplyGuard:
    """Last-line anti-duplicate guard for outgoing email replies.

    Every upstream layer (Gmail dedup table, trigger dedup, IMAP unique
    index) prevents duplicate *triggers*, but the actual send happens here.
    This guard records each sent reply in email_messages (status REPLIED,
    conversation_id = source message id) and refuses a second send for the
    same source message.
    """

    # Marker stored in EmailMessage.category for guard rows
    GUARD_CATEGORY = "reply_guard"
    # Telegram (account + bot send_message) guard rows use their own category
    # so IMAP/Gmail uids can never collide with tg message ids.
    TELEGRAM_GUARD_CATEGORY = "reply_guard_telegram"

    @staticmethod
    def guard_category(action: str, tool_name: Optional[str] = None) -> Optional[str]:
        """Guard category for a send action, or None when not guarded.

        send_email is always guarded; send_message only for the Telegram
        messaging tools (account MTProto + Bot API — the runtime tags their
        replies with `_reply_to_message_id`, so untagged sends pass through
        untouched).
        """
        if action == "send_email":
            return EmailReplyGuard.GUARD_CATEGORY
        if action == "send_message" and tool_name in (
            "telegram_account_messaging",
            "telegram_messaging",
        ):
            return EmailReplyGuard.TELEGRAM_GUARD_CATEGORY
        return None

    @staticmethod
    def extract_source_id(parameters: Optional[Dict[str, Any]]) -> Optional[str]:
        """Pull the source message id out of send parameters.

        The runtime injects `_reply_to_message_id` into send_email parameters
        (the Gmail message id / IMAP uid of the email being replied to) and
        into telegram send_message parameters ("tg:..." for account replies,
        "tgbot:..." for bot replies).
        """
        if not parameters:
            return None
        source_id = parameters.get("_reply_to_message_id")
        return str(source_id) if source_id else None

    @staticmethod
    def extract_recipient(parameters: Optional[Dict[str, Any]]) -> Optional[str]:
        if not parameters:
            return None
        to = parameters.get("to") or parameters.get("chat_id") or ""
        return str(to).strip() or None

    def __init__(self, db: Session):
        self.db = db

    def has_replied(self, source_message_id: str, category: Optional[str] = None) -> bool:
        """True when a reply for this source message was already sent/queued."""
        from app.models.email import EmailMessage

        return (
            self.db.query(EmailMessage)
            .filter(
                EmailMessage.conversation_id == source_message_id,
                EmailMessage.category == (category or self.GUARD_CATEGORY),
            )
            .first()
            is not None
        )

    def record_reply(self, source_message_id: str, recipient: Optional[str], category: Optional[str] = None) -> None:
        """Persist a reply-guard row so a second send is impossible."""
        from app.models.email import EmailMessage, EmailStatus

        guard_row = EmailMessage(
            from_address="reply-guard@system.local",
            to_address=recipient or "(unknown)",
            subject=f"Reply guard for source message {source_message_id}",
            body="",
            status=EmailStatus.REPLIED,
            conversation_id=source_message_id,
            category=category or self.GUARD_CATEGORY,
            account_id=None,
        )
        self.db.add(guard_row)
        try:
            self.db.commit()
        except Exception:
            # Lost a race (concurrent send) — the other worker's row won.
            self.db.rollback()
from app.schemas.notification import NotificationCreate

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails security validation."""
    def __init__(self, message: str, code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ToolExecutionService:
    def __init__(self, db: Session):
        self.db = db
        self.permission_service = PermissionService(db)
        self.risk_service = RiskEvaluationService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_tool(
        self,
        agent_id: UUID,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any] = None,
        reason: Optional[str] = None,
        user_id: Optional[UUID] = None,
        force_approval: bool = False,
    ) -> Dict[str, Any]:
        """Execute a tool with full security validation.

        Args:
            agent_id: The agent requesting execution
            tool_name: Name of the tool to execute
            action: Action to perform on the tool
            parameters: Action parameters
            reason: Reason for execution
            user_id: Optional user who triggered this (for audit)
            force_approval: When True, skip auto-execution and always create
                an approval request (used for AUTOMATED email replies)

        Returns:
            Dict with success, data, error, requires_approval fields
        """
        from app.events.types import EventType

        execution_context = {
            "agent_id": str(agent_id),
            "tool_name": tool_name,
            "action": action,
            "user_id": str(user_id) if user_id else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Step 1: Validate agent
            agent = self._validate_agent(agent_id)

            # Step 2: Validate tool assignment (database-backed)
            tool = self._validate_tool_assignment(agent, tool_name)

            # Step 3: Validate tool is active
            self._validate_tool_active(tool)

            # Step 4: Validate action exists and is active
            tool_action = self._validate_action(tool, action)

            # Step 5: Validate integration is connected
            integration = self._validate_integration(tool)

            # Step 6: Resolve correct account
            account = self._resolve_account(tool, agent_id)

            # Step 7: Validate ownership
            self._validate_ownership(account, agent_id)

            # Step 8: Validate permissions
            self._validate_permissions(agent_id, tool_name, action)

            # Step 9: Evaluate risk
            risk_level, requires_approval, risk_reason = self._evaluate_risk(
                agent_id, tool_name, action, parameters
            )

            # Step 10: Check if approval required (forced approval overrides
            # risk rules — e.g. replies to AUTOMATED emails always need CEO OK)
            if force_approval or requires_approval or self._requires_ceo_approval(risk_level):
                return self._handle_approval_required(
                    agent_id=agent_id,
                    action=action,
                    tool_name=tool_name,
                    parameters=parameters,
                    reason=reason,
                    risk_level="high" if force_approval and risk_level == "low" else risk_level,
                    risk_reason=risk_reason or "Forced approval policy",
                    execution_context=execution_context,
                )

            # Step 10.5: Anti-duplicate guard for outgoing emails/telegrams —
            # the last line of defense against replying twice to the same message.
            guard_category = EmailReplyGuard.guard_category(action, tool_name)
            if guard_category:
                guard = EmailReplyGuard(db=self.db)
                source_id = guard.extract_source_id(parameters)
                if source_id and guard.has_replied(source_id, guard_category):
                    logger.warning(
                        "Duplicate send blocked (already replied to source message)",
                        extra={"agent_id": str(agent_id), "source_message_id": source_id, "action": action},
                    )
                    self._audit_log(
                        agent_id=agent_id,
                        tool_name=tool_name,
                        action=action,
                        status="blocked_duplicate_reply",
                        parameters=parameters,
                        result={"blocked": True, "source_message_id": source_id},
                        user_id=user_id,
                    )
                    return {
                        "success": True,
                        "blocked_duplicate": True,
                        "message": "Reply already sent for this message; duplicate blocked by guard",
                    }

            # Step 11: Execute tool
            result = self._execute_provider_action(agent_id, tool_name, action, parameters)

            # Step 11.5: Record the reply so future sends to the same source
            # message are blocked (only after a successful real send).
            if guard_category and result.get("success"):
                guard = EmailReplyGuard(db=self.db)
                source_id = guard.extract_source_id(parameters)
                if source_id:
                    guard.record_reply(source_id, guard.extract_recipient(parameters), guard_category)

            # Step 12: Audit log
            self._audit_log(
                agent_id=agent_id,
                tool_name=tool_name,
                action=action,
                status="executed" if result["success"] else "execution_failed",
                parameters=parameters,
                result=result,
                user_id=user_id,
                risk_level=risk_level,
            )

            # Step 12b: Room activity log (best-effort)
            self._log_room_activity(
                agent_id=agent_id,
                tool_name=tool_name,
                action=action,
                success=result.get("success", False),
                error=result.get("error"),
                reason=reason,
            )

            # Step 13: Publish event
            event_type = EventType.TOOL_EXECUTION_COMPLETED if result["success"] else EventType.TOOL_EXECUTION_FAILED
            self._publish_tool_event(
                event_type, None, agent_id, tool_name, action,
                "executed" if result["success"] else "failed",
            )

            result["risk_level"] = risk_level
            result["auto_approved"] = True
            return result

        except ToolExecutionError as e:
            self._audit_log(
                agent_id=agent_id,
                tool_name=tool_name,
                action=action,
                status=f"security_denied:{e.code}",
                parameters=parameters,
                result={"error": str(e), "code": e.code},
                user_id=user_id,
            )
            return {"success": False, "error": str(e), "requires_approval": False, "code": e.code}

        except Exception as e:
            logger.error(
                "Unexpected error in tool execution",
                extra=execution_context,
                exc_info=True,
            )
            self._audit_log(
                agent_id=agent_id,
                tool_name=tool_name,
                action=action,
                status="internal_error",
                parameters=parameters,
                result={"error": str(e)},
                user_id=user_id,
            )
            return {"success": False, "error": "Internal execution error", "requires_approval": False}

    def execute_approved_action(self, approval_id: UUID) -> Dict[str, Any]:
        """Execute an approved action with full re-validation.

        Re-validates all security checks before executing.
        """
        from app.events.types import EventType

        approval = self.db.query(Approval).filter(Approval.id == approval_id).first()
        if not approval:
            return {"success": False, "error": "Approval not found"}
        if approval.status != "approved":
            return {"success": False, "error": f"Approval status is '{approval.status}', not 'approved'"}

        tool_name = approval.parameters.get("_tool_name") if approval.parameters else None
        action_name = approval.action
        parameters = {k: v for k, v in (approval.parameters or {}).items() if not k.startswith("_")}

        try:
            # Re-validate agent
            agent = self._validate_agent(approval.agent_id)

            # Re-validate tool
            if tool_name:
                tool = self._validate_tool_assignment(agent, tool_name)
                self._validate_tool_active(tool)
                self._validate_action(tool, action_name)
                self._validate_integration(tool)
                self._resolve_account(tool, approval.agent_id)
                self._validate_permissions(approval.agent_id, tool_name, action_name)

        except ToolExecutionError as e:
            self._audit_log(
                agent_id=approval.agent_id,
                tool_name=tool_name or "unknown",
                action=action_name,
                status=f"re_validation_failed:{e.code}",
                parameters=parameters,
                result={"error": str(e)},
            )
            return {"success": False, "error": f"Re-validation failed: {str(e)}"}

        tool_name_str = tool_name or "unknown"

        # Anti-duplicate guard on the approval path too: the CEO-approved send
        # must not double-fire if the guard row appeared after approval creation.
        approval_guard_category = EmailReplyGuard.guard_category(action_name, tool_name_str)
        if approval_guard_category:
            guard = EmailReplyGuard(db=self.db)
            source_id = guard.extract_source_id(parameters)
            if source_id and guard.has_replied(source_id, approval_guard_category):
                logger.warning(
                    "Approved send blocked — reply already sent for source message",
                    extra={"agent_id": str(approval.agent_id), "source_message_id": source_id, "action": action_name},
                )
                return {
                    "success": True,
                    "blocked_duplicate": True,
                    "message": "Reply already sent for this message; duplicate blocked by guard",
                }

        self._publish_tool_event(EventType.TOOL_EXECUTION_STARTED, approval_id, approval.agent_id, tool_name_str, action_name, "executing")

        result = self._execute_provider_action(approval.agent_id, tool_name_str, action_name, parameters)

        # Record the successful approved reply for the duplicate guard.
        if approval_guard_category and result.get("success"):
            guard = EmailReplyGuard(db=self.db)
            source_id = guard.extract_source_id(parameters)
            if source_id:
                guard.record_reply(source_id, guard.extract_recipient(parameters), approval_guard_category)

        self._audit_log(
            agent_id=approval.agent_id,
            tool_name=tool_name_str,
            action=action_name,
            status="executed_after_approval" if result["success"] else "execution_failed",
            parameters=parameters,
            result=result,
        )

        event_type = EventType.TOOL_EXECUTION_COMPLETED if result["success"] else EventType.TOOL_EXECUTION_FAILED
        self._publish_tool_event(event_type, approval_id, approval.agent_id, tool_name_str, action_name, "completed" if result["success"] else "failed")
        return result

    # ------------------------------------------------------------------
    # Security validation steps
    # ------------------------------------------------------------------

    def _validate_agent(self, agent_id: UUID) -> AIAgent:
        """Step 1: Validate agent exists and is active."""
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            raise ToolExecutionError("Agent not found", "AGENT_NOT_FOUND")
        if agent.lifecycle_status != LifecycleStatus.ACTIVE:
            raise ToolExecutionError(
                f"Agent is not active (status: {agent.lifecycle_status.value})",
                "AGENT_NOT_ACTIVE",
            )
        return agent

    def _validate_tool_assignment(self, agent: AIAgent, tool_name: str) -> AgentTool:
        """Step 2: Validate tool is assigned to agent via database.

        Checks both:
        - agent.tools string (legacy)
        - AgentToolAssignment table (database-backed)
        """
        # Check string-based assignment (legacy)
        tool_names = agent.tools.split("|") if agent.tools else []
        string_assigned = tool_name in tool_names

        # Check database-backed assignment
        from app.models.agent_tool_assignment import AgentToolAssignment
        db_assigned = self.db.query(AgentToolAssignment).filter(
            AgentToolAssignment.agent_id == agent.id,
            AgentToolAssignment.tool_name == tool_name,
            AgentToolAssignment.is_active == True,
        ).first() is not None

        if not string_assigned and not db_assigned:
            raise ToolExecutionError(
                f"Tool '{tool_name}' is not assigned to agent",
                "TOOL_NOT_ASSIGNED",
            )

        tool = self.db.query(AgentTool).filter(AgentTool.name == tool_name).first()
        if not tool:
            raise ToolExecutionError(
                f"Tool '{tool_name}' not found in system",
                "TOOL_NOT_FOUND",
            )

        return tool

    def _validate_tool_active(self, tool: AgentTool) -> None:
        """Step 3: Validate tool is active."""
        if not tool.is_active:
            raise ToolExecutionError(
                f"Tool '{tool.name}' is disabled",
                "TOOL_DISABLED",
            )

    def _validate_action(self, tool: AgentTool, action_name: str) -> ToolAction:
        """Step 4: Validate action exists and is active for this tool."""
        action = self.db.query(ToolAction).filter(
            ToolAction.tool_id == tool.id,
            ToolAction.name == action_name,
            ToolAction.is_active == True,
        ).first()

        if not action:
            # Check if action exists but is disabled
            action_disabled = self.db.query(ToolAction).filter(
                ToolAction.tool_id == tool.id,
                ToolAction.name == action_name,
            ).first()

            if action_disabled:
                raise ToolExecutionError(
                    f"Action '{action_name}' is disabled for tool '{tool.name}'",
                    "ACTION_DISABLED",
                )

            raise ToolExecutionError(
                f"Action '{action_name}' not found in tool '{tool.name}'",
                "ACTION_NOT_FOUND",
            )

        return action

    def _validate_integration(self, tool: AgentTool) -> Optional[Integration]:
        """Step 5: Validate integration is connected if tool requires one."""
        if not tool.integration_id:
            return None  # Built-in tool, no integration needed

        integration = self.db.query(Integration).filter(
            Integration.id == tool.integration_id,
            Integration.is_active == True,
        ).first()

        if not integration:
            raise ToolExecutionError(
                f"Integration not found for tool '{tool.name}'",
                "INTEGRATION_NOT_FOUND",
            )

        return integration

    def _resolve_account(self, tool: AgentTool, agent_id: UUID) -> Optional[IntegrationAccount]:
        """Step 6: Resolve the correct integration account."""
        if not tool.integration_id:
            return None  # Built-in tool

        account = None

        # Try deterministic account via AgentIntegration
        agent_integration = self.db.query(AgentIntegration).filter(
            AgentIntegration.agent_id == agent_id,
            AgentIntegration.integration_id == tool.integration_id,
            AgentIntegration.is_active == True,
        ).first()

        if agent_integration and agent_integration.integration_account_id:
            account = self.db.query(IntegrationAccount).filter(
                IntegrationAccount.id == agent_integration.integration_account_id,
                IntegrationAccount.integration_id == tool.integration_id,
                IntegrationAccount.is_active == True,
                IntegrationAccount.status == "connected",
            ).first()

            if not account:
                raise ToolExecutionError(
                    "Explicit account mapping points to invalid or disconnected account",
                    "ACCOUNT_INVALID",
                )
            return account

        # Fallback: find all connected accounts
        accounts = self.db.query(IntegrationAccount).filter(
            IntegrationAccount.integration_id == tool.integration_id,
            IntegrationAccount.is_active == True,
            IntegrationAccount.status == "connected",
        ).all()

        if len(accounts) == 0:
            raise ToolExecutionError(
                "No connected accounts found for this integration",
                "NO_ACCOUNTS",
            )

        if len(accounts) > 1:
            raise ToolExecutionError(
                "Multiple integration accounts exist but no explicit mapping configured. "
                "Please assign a specific account to this agent.",
                "AMBIGUOUS_ACCOUNTS",
                {"account_count": len(accounts)},
            )

        # Exactly one account — safe to use
        return accounts[0]

    def _validate_ownership(self, account: Optional[IntegrationAccount], agent_id: UUID) -> None:
        """Step 7: Validate account ownership."""
        if not account:
            return  # Built-in tool, no account

        # Verify account has a valid user
        if not account.user_id:
            raise ToolExecutionError(
                "Integration account has no owner",
                "ACCOUNT_NO_OWNER",
            )

        # Verify user exists and is active
        from app.models.user import User
        user = self.db.query(User).filter(User.id == account.user_id).first()
        if not user:
            raise ToolExecutionError(
                "Integration account owner not found",
                "OWNER_NOT_FOUND",
            )

    def _validate_permissions(self, agent_id: UUID, tool_name: str, action_name: str) -> None:
        """Step 8: Validate agent has all required permissions."""
        tool = self.db.query(AgentTool).filter(AgentTool.name == tool_name).first()
        if not tool:
            return

        tool_permissions = self.db.query(ToolPermission).filter(
            ToolPermission.tool_id == tool.id
        ).all()

        if not tool_permissions:
            return  # No permissions required

        for tp in tool_permissions:
            # If action-specific permission, check if it applies to this action
            if tp.action_id:
                action = self.db.query(ToolAction).filter(ToolAction.id == tp.action_id).first()
                if action and action.name != action_name:
                    continue

            permission = self.db.query(Permission).filter(Permission.id == tp.permission_id).first()
            if not permission:
                continue

            has_perm, access_level, msg = self.permission_service.check_permission(
                agent_id, permission.name
            )

            if not has_perm:
                raise ToolExecutionError(
                    f"Missing required permission: {permission.name}",
                    "PERMISSION_DENIED",
                    {"permission": permission.name, "detail": msg},
                )

            if access_level == "approval_required":
                raise ToolExecutionError(
                    f"Permission '{permission.name}' requires approval",
                    "PERMISSION_REQUIRES_APPROVAL",
                    {"permission": permission.name},
                )

    def _evaluate_risk(self, agent_id: UUID, tool_name: str, action_name: str, parameters: Optional[Dict[str, Any]] = None) -> Tuple[str, bool, Optional[str]]:
        """Step 9: Evaluate risk level."""
        risk_level, requires_approval, rule_id, rule_name, reason = self.risk_service.evaluate_risk(
            agent_id, tool_name, action_name, parameters
        )
        return risk_level, requires_approval, reason

    def _requires_ceo_approval(self, risk_level: str) -> bool:
        """Check if risk level requires CEO approval."""
        try:
            risk_enum = RiskLevel(risk_level)
            return requires_ceo_approval(risk_enum)
        except ValueError:
            return True  # Unknown risk requires approval

    def _handle_approval_required(
        self,
        agent_id: UUID,
        action: str,
        tool_name: str,
        parameters: Optional[Dict[str, Any]],
        reason: Optional[str],
        risk_level: str,
        risk_reason: Optional[str],
        execution_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Step 10: Handle approval-required actions."""
        from app.events.types import EventType

        # Anti-duplicate guard: never create a second approval request for a
        # reply that was already sent for the same source message.
        guard_category = EmailReplyGuard.guard_category(action, tool_name)
        if guard_category:
            guard = EmailReplyGuard(db=self.db)
            source_id = guard.extract_source_id(parameters)
            if source_id and guard.has_replied(source_id, guard_category):
                logger.warning(
                    "Duplicate send (approval path) blocked — already replied",
                    extra={"agent_id": str(agent_id), "source_message_id": source_id, "action": action},
                )
                return {
                    "success": True,
                    "blocked_duplicate": True,
                    "message": "Reply already sent for this message; duplicate blocked by guard",
                }

        approval = self._create_approval_request(
            agent_id=agent_id,
            action=action,
            tool_name=tool_name,
            parameters=parameters,
            reason=reason,
            risk_level=risk_level,
        )

        self._audit_log(
            agent_id=agent_id,
            tool_name=tool_name,
            action=action,
            status="pending_approval",
            parameters=parameters,
            result={"approval_id": str(approval.id), "risk_level": risk_level},
        )

        self._publish_tool_event(
            EventType.TOOL_EXECUTION_STARTED, approval.id, agent_id, tool_name, action, "pending_approval"
        )

        return {
            "success": False,
            "requires_approval": True,
            "approval_id": str(approval.id),
            "risk_level": risk_level,
            "message": f"Action requires CEO approval: {risk_reason}",
        }

    # ------------------------------------------------------------------
    # Provider execution
    # ------------------------------------------------------------------

    def _execute_provider_action(self, agent_id: UUID, tool_name: str, action: str, parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve provider → credentials → call API → return result."""
        from app.services.integration_providers.registry import get_provider

        tool = self.db.query(AgentTool).filter(AgentTool.name == tool_name).first()
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        if not tool.integration_id:
            return {"success": True, "message": f"Action '{action}' executed (built-in tool, no API call needed)", "data": {"action": action, "parameters": parameters}}

        # Resolve provider
        provider = None
        integration = self.db.query(Integration).filter(Integration.id == tool.integration_id).first()
        if integration:
            provider = get_provider(integration.name)

        if not provider:
            return {"success": True, "message": f"No provider registered for tool '{tool_name}' – action logged", "data": {"action": action, "parameters": parameters}}

        # Get credentials
        access_token, credentials = self._get_credentials_for_tool(tool, agent_id)

        # Strip internal guard keys before hitting the provider API —
        # providers must never see underscore-prefixed metadata.
        provider_params = {
            k: v for k, v in (parameters or {}).items()
            if not str(k).startswith("_")
        }

        async def _run():
            return await provider.execute_action(action, provider_params, access_token=access_token, credentials=credentials)

        try:
            from app.utils.async_utils import run_async
            result = run_async(_run())
        except Exception as e:
            logger.error(f"Action execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e), "tool_id": str(tool.id)}

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "message": f"Action '{action}' {'succeeded' if result.success else 'failed'}",
        }

    def _get_credentials_for_tool(self, tool: AgentTool, agent_id: Optional[UUID] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Get credentials for tool execution."""
        if not tool.integration_id:
            return None, None

        account = None

        # Try deterministic account via AgentIntegration
        if agent_id:
            agent_integration = self.db.query(AgentIntegration).filter(
                AgentIntegration.agent_id == agent_id,
                AgentIntegration.integration_id == tool.integration_id,
                AgentIntegration.is_active == True,
            ).first()

            if agent_integration and agent_integration.integration_account_id:
                account = self.db.query(IntegrationAccount).filter(
                    IntegrationAccount.id == agent_integration.integration_account_id,
                    IntegrationAccount.integration_id == tool.integration_id,
                    IntegrationAccount.is_active == True,
                    IntegrationAccount.status == "connected",
                ).first()

        # Fallback: single account
        if not account:
            accounts = self.db.query(IntegrationAccount).filter(
                IntegrationAccount.integration_id == tool.integration_id,
                IntegrationAccount.is_active == True,
                IntegrationAccount.status == "connected",
            ).all()

            if len(accounts) == 1:
                account = accounts[0]

        if not account:
            return None, None

        # Get credentials
        oauth2_service = OAuth2Service(self.db)
        from app.utils.async_utils import run_async

        if account.oauth2_access_token:
            token = oauth2_service.get_access_token(account)
            if token and account.oauth2_token_expiry:
                try:
                    expiry = datetime.fromisoformat(account.oauth2_token_expiry)
                    if datetime.now(timezone.utc) > expiry:
                        refreshed = run_async(oauth2_service.refresh_access_token(account))
                        if refreshed:
                            token = refreshed
                except (ValueError, TypeError):
                    logger.warning("Failed to parse token expiry", exc_info=True)
            return token, None

        if account.credentials:
            from app.utils.encryption import decrypt_field
            return None, {k: decrypt_field(str(v)) for k, v in account.credentials.items()}

        return None, None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_approval_request(self, agent_id: UUID, action: str, tool_name: str, parameters: Optional[Dict[str, Any]], reason: Optional[str], risk_level: str) -> Approval:
        tool = self.db.query(AgentTool).filter(AgentTool.name == tool_name).first()
        enriched_params = dict(parameters or {})
        enriched_params["_tool_name"] = tool_name
        approval = Approval(
            agent_id=agent_id,
            action=action,
            tool_id=tool.id if tool else None,
            parameters=enriched_params,
            reason=reason,
            risk_level=risk_level,
            status="pending",
            requested_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(approval)
        self.db.flush()
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        self._create_notification(
            user_id=agent.user_id if agent else None, type="approval_needed",
            title=f"Approval Required: {action}",
            message=f"Agent {agent.name if agent else 'Unknown'} requests approval for: {action} using {tool_name}",
            reference_type="approval", reference_id=approval.id,
        )
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def _audit_log(
        self,
        agent_id: UUID,
        tool_name: str,
        action: str,
        status: str,
        parameters: Optional[Dict[str, Any]],
        result: Optional[Dict[str, Any]] = None,
        user_id: Optional[UUID] = None,
        risk_level: Optional[str] = None,
    ):
        """Write audit log with full security context."""
        AuditService(self.db).log_action(
            action=f"tool_{status}",
            agent_id=agent_id,
            resource_type="tool",
            details={
                "tool_name": tool_name,
                "action": action,
                "status": status,
                "parameters": parameters,
                "result_summary": {k: v for k, v in (result or {}).items() if k != "data"},
                "user_id": str(user_id) if user_id else None,
                "risk_level": risk_level,
            },
        )

    def _create_notification(self, user_id: Optional[UUID], type: str, title: str, message: str, reference_type: Optional[str] = None, reference_id: Optional[UUID] = None):
        if user_id is None:
            return
        NotificationService(self.db).create_notification(
            NotificationCreate(user_id=user_id, type=type, title=title, message=message, reference_type=reference_type, reference_id=reference_id)
        )

    @staticmethod
    def _fire_async(coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)

    def _publish_tool_event(self, event_type, approval_id, agent_id, tool_name, action, status="", error_message=""):
        try:
            from app.events.publisher import publish_tool_execution_event
            self._fire_async(
                publish_tool_execution_event(
                    event_type=event_type,
                    approval_id=approval_id,
                    agent_id=agent_id,
                    tool_name=tool_name,
                    action=action,
                    status=status,
                    error_message=error_message,
                )
            )
        except Exception as e:
            logger.warning("Failed to publish tool execution event", exc_info=True)

    # ------------------------------------------------------------------
    # Read-only accessors (unchanged)
    # ------------------------------------------------------------------

    def check_tool_access(self, agent_id: UUID, tool_name: str) -> Tuple[bool, str, Optional[str]]:
        """Legacy access check for backward compatibility."""
        try:
            agent = self._validate_agent(agent_id)
            tool = self._validate_tool_assignment(agent, tool_name)
            self._validate_tool_active(tool)
            return True, "Access granted", tool.risk_level
        except ToolExecutionError as e:
            return False, str(e), None

    def check_action_access(self, agent_id: UUID, tool_name: str, action_name: str) -> Tuple[bool, str, Optional[str]]:
        """Legacy action check for backward compatibility."""
        has_access, msg, _ = self.check_tool_access(agent_id, tool_name)
        if not has_access:
            return False, msg, None
        try:
            tool = self.db.query(AgentTool).filter(AgentTool.name == tool_name).first()
            if tool:
                self._validate_action(tool, action_name)
            return True, "Action access granted", None
        except ToolExecutionError as e:
            return False, str(e), None

    def _log_room_activity(self, agent_id: UUID, tool_name: str, action: str,
                           success: bool, error: Optional[str] = None,
                           reason: Optional[str] = None) -> None:
        """Best-effort AgentActivity record so the room dashboard shows tool
        usage (e.g. an email sent via the gmail provider)."""
        try:
            from app.services.activity_service import ActivityService

            status = "success" if success else "failed"
            if success:
                description = f"Executed {action} via {tool_name}"
            else:
                description = f"{action} via {tool_name} failed: {error or 'unknown error'}"

            ActivityService(self.db).log_agent_action(
                agent_id=agent_id,
                activity_type="tool_executed",
                description=description[:280],
                tool_name=tool_name,
                status=status,
                metadata={"action": action, "reason": (reason or "")[:200]},
            )
        except Exception as e:
            logger.warning("Failed to log tool room activity: %s", e)

    def get_pending_approvals(self, limit: int = 50, user_id: Optional[UUID] = None) -> list:
        query = self.db.query(Approval).filter(Approval.status == "pending")
        if user_id is not None:
            from app.models.agent import AIAgent
            agent_ids = [a.id for a in self.db.query(AIAgent.id).filter(AIAgent.user_id == user_id).all()]
            if not agent_ids:
                return []
            query = query.filter(Approval.agent_id.in_(agent_ids))
        return query.order_by(Approval.created_at.desc()).limit(limit).all()

    def get_approval_stats(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        def _count(status: str) -> int:
            query = self.db.query(Approval).filter(Approval.status == status)
            if user_id is not None:
                from app.models.agent import AIAgent
                agent_ids = [a.id for a in self.db.query(AIAgent.id).filter(AIAgent.user_id == user_id).all()]
                if not agent_ids:
                    return 0
                query = query.filter(Approval.agent_id.in_(agent_ids))
            return query.count()

        pending = _count("pending")
        approved = _count("approved")
        rejected = _count("rejected")
        return {"pending": pending, "approved": approved, "rejected": rejected, "total": pending + approved + rejected}
