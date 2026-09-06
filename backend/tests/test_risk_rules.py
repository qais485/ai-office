"""Tests for the Risk Rules system: CRUD, evaluation, priority, risk levels, and approval integration."""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.core.config import settings
from app.core.risk_levels import RiskLevel, should_auto_approve, requires_ceo_approval
from app.models.risk_rule import RiskRule
from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.schemas.risk_rule import (
    RiskRuleCreate, RiskRuleUpdate, RiskRuleResponse,
    RiskEvaluationRequest, RiskEvaluationResponse,
)
from app.services.risk_rule_service import RiskRuleService, RiskEvaluationService


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
def rule_service(db):
    return RiskRuleService(db)


@pytest.fixture
def eval_service(db):
    return RiskEvaluationService(db)


# ------------------------------------------------------------------
# Schema Tests
# ------------------------------------------------------------------

class TestRiskRuleSchemas:
    def test_create_valid_rule(self):
        rule = RiskRuleCreate(name="Test Rule", risk_level="high")
        assert rule.name == "Test Rule"
        assert rule.risk_level == RiskLevel.HIGH
        assert rule.requires_approval is False
        assert rule.priority == 0
        assert rule.is_active is True

    def test_create_defaults(self):
        rule = RiskRuleCreate(name="Default Rule")
        assert rule.risk_level == RiskLevel.MEDIUM
        assert rule.conditions is None
        assert rule.action_name is None
        assert rule.tool_id is None

    def test_risk_level_validates_enum(self):
        rule = RiskRuleCreate(name="Test", risk_level="critical")
        assert rule.risk_level == RiskLevel.CRITICAL

    def test_risk_level_rejects_invalid(self):
        with pytest.raises(Exception):
            RiskRuleCreate(name="Test", risk_level="banana")

    def test_name_cannot_be_blank(self):
        with pytest.raises(Exception):
            RiskRuleCreate(name="")

    def test_name_cannot_be_whitespace(self):
        with pytest.raises(Exception):
            RiskRuleCreate(name="   ")

    def test_update_partial(self):
        update = RiskRuleUpdate(risk_level="high")
        data = update.model_dump(exclude_unset=True)
        assert data == {"risk_level": RiskLevel.HIGH}
        assert "name" not in data

    def test_update_empty(self):
        update = RiskRuleUpdate()
        data = update.model_dump(exclude_unset=True)
        assert data == {}

    def test_valid_conditions(self):
        rule = RiskRuleCreate(
            name="Test",
            conditions={"amount": {"min": 100, "max": 5000}}
        )
        assert rule.conditions == {"amount": {"min": 100, "max": 5000}}

    def test_invalid_conditions_operator(self):
        with pytest.raises(Exception):
            RiskRuleCreate(
                name="Test",
                conditions={"amount": {"regex": ".*"}}
            )

    def test_response_from_attributes(self):
        rule = RiskRuleResponse(
            id=uuid4(),
            name="Test",
            risk_level="medium",
            requires_approval=False,
            priority=0,
            is_active=True,
            created_at="2024-01-01T00:00:00",
        )
        assert str(rule.id)


# ------------------------------------------------------------------
# RiskLevel Enum Tests
# ------------------------------------------------------------------

class TestRiskLevel:
    def test_all_levels_exist(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_auto_approve_low(self):
        assert should_auto_approve(RiskLevel.LOW) is True

    def test_auto_approve_medium(self):
        assert should_auto_approve(RiskLevel.MEDIUM) is True

    def test_auto_approve_high(self):
        assert should_auto_approve(RiskLevel.HIGH) is False

    def test_auto_approve_critical(self):
        assert should_auto_approve(RiskLevel.CRITICAL) is False

    def test_ceo_approval_low(self):
        assert requires_ceo_approval(RiskLevel.LOW) is False

    def test_ceo_approval_high(self):
        assert requires_ceo_approval(RiskLevel.HIGH) is True

    def test_ceo_approval_critical(self):
        assert requires_ceo_approval(RiskLevel.CRITICAL) is True


# ------------------------------------------------------------------
# CRUD Tests (using real DB with transaction rollback)
# ------------------------------------------------------------------

class TestRiskRuleCRUD:
    def test_create_rule(self, rule_service, db):
        data = RiskRuleCreate(name="Send Email Rule", action_name="send_email", risk_level="medium")
        rule = rule_service.create_risk_rule(data)
        assert rule.name == "Send Email Rule"
        assert rule.action_name == "send_email"
        assert rule.risk_level == "medium"
        assert rule.id is not None

    def test_get_rule(self, rule_service, db):
        data = RiskRuleCreate(name="Get Test", risk_level="low")
        created = rule_service.create_risk_rule(data)
        fetched = rule_service.get_risk_rule(created.id)
        assert fetched is not None
        assert fetched.name == "Get Test"

    def test_get_nonexistent_rule(self, rule_service):
        result = rule_service.get_risk_rule(uuid4())
        assert result is None

    def test_list_rules_active_only(self, rule_service, db):
        r1 = rule_service.create_risk_rule(RiskRuleCreate(name="Active", is_active=True))
        r2 = rule_service.create_risk_rule(RiskRuleCreate(name="Inactive", is_active=False))
        active = rule_service.get_risk_rules(active_only=True)
        names = [r.name for r in active]
        assert "Active" in names
        assert "Inactive" not in names

    def test_list_all_rules(self, rule_service, db):
        rule_service.create_risk_rule(RiskRuleCreate(name="A", is_active=True))
        rule_service.create_risk_rule(RiskRuleCreate(name="B", is_active=False))
        all_rules = rule_service.get_risk_rules(active_only=False)
        assert len(all_rules) >= 2

    def test_update_rule(self, rule_service, db):
        created = rule_service.create_risk_rule(RiskRuleCreate(name="Original", risk_level="low"))
        updated = rule_service.update_risk_rule(created.id, RiskRuleUpdate(name="Updated", risk_level="high"))
        assert updated.name == "Updated"
        assert updated.risk_level == "high"

    def test_delete_rule(self, rule_service, db):
        created = rule_service.create_risk_rule(RiskRuleCreate(name="To Delete"))
        result = rule_service.delete_risk_rule(created.id)
        assert result is True
        assert rule_service.get_risk_rule(created.id) is None

    def test_delete_nonexistent(self, rule_service):
        result = rule_service.delete_risk_rule(uuid4())
        assert result is False

    def test_rules_ordered_by_priority_desc(self, rule_service, db):
        rule_service.create_risk_rule(RiskRuleCreate(name="Low Priority", priority=1))
        rule_service.create_risk_rule(RiskRuleCreate(name="High Priority", priority=10))
        rules = rule_service.get_risk_rules(active_only=True)
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities, reverse=True)


# ------------------------------------------------------------------
# Evaluation Tests
# ------------------------------------------------------------------

class TestRiskEvaluation:
    def test_no_rules_returns_medium_default(self, eval_service, agent_id=None):
        aid = agent_id or uuid4()
        level, requires, rule_id, rule_name, reason = eval_service.evaluate_risk(
            aid, "unknown_tool", "unknown_action"
        )
        assert level == RiskLevel.MEDIUM.value
        assert requires is False
        assert rule_id is None
        assert "default" in reason.lower()

    def test_rule_matches_action_name(self, eval_service, db):
        rule = eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="High Risk Refund",
                action_name="issue_refund",
                risk_level="high",
                requires_approval=True,
            )
        )
        aid = uuid4()
        level, requires, rule_id, rule_name, reason = eval_service.evaluate_risk(
            aid, "payment_tool", "issue_refund"
        )
        assert level == "high"
        assert requires is True
        assert rule_id == rule.id
        assert "High Risk Refund" in reason

    def test_rule_matches_tool_id(self, eval_service, db):
        tool = AgentTool(name="email_writer", display_name="Email Writer", risk_level="low")
        db.add(tool)
        db.flush()

        rule = eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Email Tool Rule",
                tool_id=tool.id,
                risk_level="medium",
            )
        )
        aid = uuid4()
        level, requires, rule_id, rule_name, reason = eval_service.evaluate_risk(
            aid, "email_writer", "send_email"
        )
        assert rule_id == rule.id

    def test_rule_does_not_match_wrong_action(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Refund Only",
                action_name="issue_refund",
                risk_level="critical",
            )
        )
        aid = uuid4()
        level, requires, rule_id, rule_name, reason = eval_service.evaluate_risk(
            aid, "payment_tool", "send_email"
        )
        assert rule_id is None  # No rule matched

    def test_empty_rule_matches_nothing(self, eval_service, db):
        """A rule with no action, tool, or conditions must NOT match anything."""
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(name="Empty Rule", risk_level="low")
        )
        aid = uuid4()
        level, requires, rule_id, rule_name, reason = eval_service.evaluate_risk(
            aid, "any_tool", "any_action"
        )
        assert rule_id is None  # Empty rule should not match

    def test_priority_determines_match_order(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(name="Low Priority", action_name="send_email", risk_level="low", priority=1)
        )
        high = eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(name="High Priority", action_name="send_email", risk_level="critical", priority=100)
        )
        aid = uuid4()
        level, requires, rule_id, rule_name, reason = eval_service.evaluate_risk(
            aid, "email_tool", "send_email"
        )
        assert rule_id == high.id
        assert level == "critical"

    def test_conditions_match(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Large Refund",
                action_name="issue_refund",
                risk_level="critical",
                conditions={"amount": {"min": 1000}},
            )
        )
        aid = uuid4()
        level, requires, rule_id, _, _ = eval_service.evaluate_risk(
            aid, "payment_tool", "issue_refund", {"amount": 5000}
        )
        assert rule_id is not None
        assert level == "critical"

    def test_conditions_no_match(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Large Refund Only",
                action_name="issue_refund",
                risk_level="critical",
                conditions={"amount": {"min": 1000}},
            )
        )
        aid = uuid4()
        rule_id = eval_service.evaluate_risk(
            aid, "payment_tool", "issue_refund", {"amount": 50}
        )[2]
        assert rule_id is None  # Condition not met, rule doesn't match

    def test_conditions_missing_parameter(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Needs Amount",
                action_name="issue_refund",
                risk_level="high",
                conditions={"amount": {"min": 100}},
            )
        )
        aid = uuid4()
        rule_id = eval_service.evaluate_risk(
            aid, "payment_tool", "issue_refund", {}
        )[2]
        assert rule_id is None

    def test_condition_type_coercion_error(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Numeric Check",
                action_name="issue_refund",
                risk_level="high",
                conditions={"amount": {"min": 100}},
            )
        )
        aid = uuid4()
        rule_id = eval_service.evaluate_risk(
            aid, "payment_tool", "issue_refund", {"amount": "not_a_number"}
        )[2]
        assert rule_id is None  # float("not_a_number") raises ValueError

    def test_condition_equals(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Type Check",
                action_name="process",
                risk_level="low",
                conditions={"type": "internal"},
            )
        )
        aid = uuid4()
        rule_id = eval_service.evaluate_risk(
            aid, "tool", "process", {"type": "internal"}
        )[2]
        assert rule_id is not None

    def test_condition_contains(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Contains Check",
                action_name="send",
                risk_level="medium",
                conditions={"subject": {"contains": "URGENT"}},
            )
        )
        aid = uuid4()
        rule_id = eval_service.evaluate_risk(
            aid, "tool", "send", {"subject": "URGENT: Server down"}
        )[2]
        assert rule_id is not None

    def test_fallback_to_tool_risk_level(self, eval_service, db):
        tool = AgentTool(name="my_tool", display_name="My Tool", risk_level="high", requires_approval=True)
        db.add(tool)
        db.flush()

        aid = uuid4()
        level, requires, rule_id, _, reason = eval_service.evaluate_risk(
            aid, "my_tool", "some_action"
        )
        assert level == "high"
        assert requires is True
        assert rule_id is None
        assert "tool default" in reason.lower()

    def test_fallback_to_tool_action_risk_level(self, eval_service, db):
        tool = AgentTool(name="my_tool", display_name="My Tool", risk_level="low")
        db.add(tool)
        db.flush()

        action = ToolAction(tool_id=tool.id, name="risky_action", display_name="Risky Action", risk_level="critical", requires_approval=True)
        db.add(action)
        db.flush()

        aid = uuid4()
        level, requires, rule_id, _, reason = eval_service.evaluate_risk(
            aid, "my_tool", "risky_action"
        )
        assert level == "critical"
        assert requires is True
        assert rule_id is None
        assert "tool action" in reason.lower()


# ------------------------------------------------------------------
# Summary Tests
# ------------------------------------------------------------------

class TestRiskSummary:
    def test_summary_counts(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(name="R1", risk_level="low", is_active=True)
        )
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(name="R2", risk_level="high", requires_approval=True, is_active=True)
        )
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(name="R3", risk_level="critical", requires_approval=True, is_active=False)
        )

        summary = eval_service.get_risk_summary()
        assert summary["total_rules"] == 3
        assert summary["active_rules"] == 2
        assert summary["by_risk_level"]["low"] == 1
        assert summary["by_risk_level"]["high"] == 1
        assert summary["by_risk_level"]["critical"] == 1
        assert summary["approval_required"] == 2


# ------------------------------------------------------------------
# Integration with Tool Execution (mock-based)
# ------------------------------------------------------------------

class TestToolExecutionIntegration:
    def test_risk_rule_overrides_tool_default(self, eval_service, db):
        tool = AgentTool(name="email_tool", display_name="Email", risk_level="low")
        db.add(tool)
        db.flush()

        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Block Mass Email",
                action_name="send_bulk",
                risk_level="critical",
                requires_approval=True,
            )
        )

        aid = uuid4()
        level, requires, rule_id, _, _ = eval_service.evaluate_risk(
            aid, "email_tool", "send_bulk"
        )
        assert level == "critical"
        assert requires is True
        assert rule_id is not None

    def test_inactive_rule_not_evaluated(self, eval_service, db):
        eval_service.rule_service.create_risk_rule(
            RiskRuleCreate(
                name="Disabled Rule",
                action_name="issue_refund",
                risk_level="critical",
                requires_approval=True,
                is_active=False,
            )
        )

        aid = uuid4()
        rule_id = eval_service.evaluate_risk(
            aid, "payment_tool", "issue_refund"
        )[2]
        assert rule_id is None  # Inactive rule should not match
