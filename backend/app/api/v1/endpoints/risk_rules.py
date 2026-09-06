from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.risk_rule import RiskRuleCreate, RiskRuleUpdate, RiskRuleResponse, RiskEvaluationRequest, RiskEvaluationResponse
from app.services.risk_rule_service import RiskRuleService, RiskEvaluationService
from app.api.deps import require_role
from app.models.user import User, UserRole

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[RiskRuleResponse])
async def get_risk_rules(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = RiskRuleService(db)
    rules = service.get_risk_rules(active_only=active_only)
    logger.debug("Listed %d risk rules", len(rules))
    return rules


@router.get("/summary")
async def get_risk_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = RiskEvaluationService(db)
    return service.get_risk_summary()


@router.get("/{rule_id}", response_model=RiskRuleResponse)
async def get_risk_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = RiskRuleService(db)
    rule = service.get_risk_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Risk rule not found")
    logger.debug("Retrieved risk rule %s", rule_id)
    return rule


@router.post("/", response_model=RiskRuleResponse)
async def create_risk_rule(
    rule: RiskRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO))
):
    service = RiskRuleService(db)
    created = service.create_risk_rule(rule)
    logger.info("Created risk rule %s", created.id)
    return created


@router.put("/{rule_id}", response_model=RiskRuleResponse)
async def update_risk_rule(
    rule_id: UUID,
    rule: RiskRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO))
):
    service = RiskRuleService(db)
    updated = service.update_risk_rule(rule_id, rule)
    if not updated:
        raise HTTPException(status_code=404, detail="Risk rule not found")
    logger.info("Updated risk rule %s", rule_id)
    return updated


@router.delete("/{rule_id}")
async def delete_risk_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO))
):
    service = RiskRuleService(db)
    if not service.delete_risk_rule(rule_id):
        raise HTTPException(status_code=404, detail="Risk rule not found")
    logger.info("Deleted risk rule %s", rule_id)
    return {"message": "Risk rule deleted"}


@router.post("/evaluate", response_model=RiskEvaluationResponse)
async def evaluate_risk(
    request: RiskEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = RiskEvaluationService(db)
    risk_level, requires_approval, rule_id, rule_name, reason = service.evaluate_risk(
        request.agent_id,
        request.tool_name,
        request.action_name,
        request.parameters
    )
    logger.info("Evaluated risk for agent %s tool %s: %s", request.agent_id, request.tool_name, risk_level)
    return RiskEvaluationResponse(
        risk_level=risk_level,
        requires_approval=requires_approval,
        rule_id=rule_id,
        rule_name=rule_name,
        reason=reason
    )
