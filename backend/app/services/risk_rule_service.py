import logging
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.risk_rule import RiskRule
from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.schemas.risk_rule import RiskRuleCreate, RiskRuleUpdate
from app.core.risk_levels import RiskLevel

logger = logging.getLogger(__name__)


class RiskRuleService:
    def __init__(self, db: Session):
        self.db = db

    def get_risk_rules(self, active_only: bool = True) -> List[RiskRule]:
        query = self.db.query(RiskRule)
        if active_only:
            query = query.filter(RiskRule.is_active == True)
        return query.order_by(RiskRule.priority.desc(), RiskRule.created_at.desc()).all()

    def get_risk_rule(self, rule_id: UUID) -> Optional[RiskRule]:
        return self.db.query(RiskRule).filter(RiskRule.id == rule_id).first()

    def create_risk_rule(self, data: RiskRuleCreate) -> RiskRule:
        rule = RiskRule(**data.model_dump())
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def update_risk_rule(self, rule_id: UUID, data: RiskRuleUpdate) -> Optional[RiskRule]:
        rule = self.get_risk_rule(rule_id)
        if not rule:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(rule, key, value)

        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete_risk_rule(self, rule_id: UUID) -> bool:
        rule = self.get_risk_rule(rule_id)
        if not rule:
            return False

        self.db.delete(rule)
        self.db.commit()
        return True


class RiskEvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.rule_service = RiskRuleService(db)

    def evaluate_risk(
        self,
        agent_id: UUID,
        tool_name: str,
        action_name: str,
        parameters: Optional[dict] = None
    ) -> Tuple[str, bool, Optional[UUID], Optional[str], str]:
        rules = self.rule_service.get_risk_rules(active_only=True)

        for rule in rules:
            if self._matches_rule(rule, tool_name, action_name, parameters):
                return (
                    rule.risk_level,
                    rule.requires_approval,
                    rule.id,
                    rule.name,
                    f"Matched rule: {rule.name}"
                )

        tool = self.db.query(AgentTool).filter(AgentTool.name == tool_name).first()
        if tool:
            action = self.db.query(ToolAction).filter(
                ToolAction.tool_id == tool.id,
                ToolAction.name == action_name
            ).first()

            if action:
                return (
                    action.risk_level,
                    action.requires_approval,
                    None,
                    None,
                    f"Using tool action risk level: {action.risk_level}"
                )

            return (
                tool.risk_level,
                tool.requires_approval,
                None,
                None,
                f"Using tool default risk level: {tool.risk_level}"
            )

        return (
            RiskLevel.MEDIUM.value,
            False,
            None,
            None,
            "No matching rule found, using default medium risk"
        )

    def _matches_rule(
        self,
        rule: RiskRule,
        tool_name: str,
        action_name: str,
        parameters: Optional[dict]
    ) -> bool:
        has_action = rule.action_name is not None
        has_tool = rule.tool_id is not None
        has_conditions = rule.conditions is not None and len(rule.conditions) > 0

        if not has_action and not has_tool and not has_conditions:
            return False

        if has_action and rule.action_name != action_name:
            return False

        if has_tool:
            tool = self.db.query(AgentTool).filter(AgentTool.id == rule.tool_id).first()
            if not tool or tool.name != tool_name:
                return False

        if has_conditions:
            if not self._check_conditions(rule.conditions, parameters):
                return False

        return True

    def _check_conditions(self, conditions: dict, parameters: Optional[dict]) -> bool:
        if not parameters:
            return False

        for key, condition in conditions.items():
            if key not in parameters:
                return False

            value = parameters[key]

            try:
                if isinstance(condition, dict):
                    if "min" in condition and float(value) < float(condition["min"]):
                        return False
                    if "max" in condition and float(value) > float(condition["max"]):
                        return False
                    if "equals" in condition and value != condition["equals"]:
                        return False
                    if "contains" in condition and condition["contains"] not in str(value):
                        return False
                else:
                    if value != condition:
                        return False
            except (ValueError, TypeError) as e:
                logger.warning(f"Condition check failed for key '{key}': {e}")
                return False

        return True

    def get_risk_summary(self) -> dict:
        rules = self.rule_service.get_risk_rules(active_only=False)

        summary = {
            "total_rules": len(rules),
            "active_rules": len([r for r in rules if r.is_active]),
            "by_risk_level": {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0
            },
            "approval_required": 0
        }

        for rule in rules:
            if rule.risk_level in summary["by_risk_level"]:
                summary["by_risk_level"][rule.risk_level] += 1
            if rule.requires_approval:
                summary["approval_required"] += 1

        return summary
