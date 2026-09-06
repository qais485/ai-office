from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, field_validator
from uuid import UUID

from app.core.risk_levels import RiskLevel


class RiskRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    action_name: Optional[str] = None
    tool_id: Optional[UUID] = None
    risk_level: RiskLevel = RiskLevel.MEDIUM
    requires_approval: bool = False
    conditions: Optional[dict] = None
    priority: int = 0
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Rule name cannot be blank")
        return v.strip()

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("Conditions must be a dictionary")
        for key, condition in v.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Condition keys must be non-empty strings")
            if isinstance(condition, dict):
                supported_ops = {"min", "max", "equals", "contains"}
                for op in condition:
                    if op not in supported_ops:
                        raise ValueError(
                            f"Unsupported condition operator '{op}'. "
                            f"Supported: {', '.join(sorted(supported_ops))}"
                        )
        return v


class RiskRuleCreate(RiskRuleBase):
    pass


class RiskRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    action_name: Optional[str] = None
    tool_id: Optional[UUID] = None
    risk_level: Optional[RiskLevel] = None
    requires_approval: Optional[bool] = None
    conditions: Optional[dict] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Rule name cannot be blank")
        return v.strip() if v else v

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("Conditions must be a dictionary")
        for key, condition in v.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Condition keys must be non-empty strings")
            if isinstance(condition, dict):
                supported_ops = {"min", "max", "equals", "contains"}
                for op in condition:
                    if op not in supported_ops:
                        raise ValueError(
                            f"Unsupported condition operator '{op}'. "
                            f"Supported: {', '.join(sorted(supported_ops))}"
                        )
        return v


class RiskRuleResponse(RiskRuleBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RiskEvaluationRequest(BaseModel):
    agent_id: UUID
    tool_name: str
    action_name: str
    parameters: Optional[dict] = None


class RiskEvaluationResponse(BaseModel):
    risk_level: RiskLevel
    requires_approval: bool
    rule_id: Optional[UUID] = None
    rule_name: Optional[str] = None
    reason: str
