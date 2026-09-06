"""Agent Trigger API — CRUD, manual fire, and execution history."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ------------------------------------------------------------------
# Request/Response schemas
# ------------------------------------------------------------------

class CreateTriggerRequest(BaseModel):
    agent_id: str
    trigger_type: str  # manual, scheduled, integration, room
    payload: Optional[dict] = None
    source_event_type: Optional[str] = None
    source_event_id: Optional[str] = None
    match_integration: Optional[str] = None
    match_event_type: Optional[str] = None
    match_room_id: Optional[str] = None
    schedule_interval_seconds: Optional[int] = None
    cooldown_seconds: int = 30


class ManualTriggerRequest(BaseModel):
    agent_id: str
    instruction: str
    payload: Optional[dict] = None


class UpdateTriggerRequest(BaseModel):
    is_active: Optional[bool] = None
    cooldown_seconds: Optional[int] = None
    schedule_interval_seconds: Optional[int] = None
    payload: Optional[dict] = None


# ------------------------------------------------------------------
# CRUD endpoints
# ------------------------------------------------------------------

@router.get("/")
async def list_triggers(
    agent_id: Optional[str] = Query(None),
    trigger_type: Optional[str] = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService
    from app.models.agent_trigger import TriggerType

    service = TriggerService(db)
    agent_uuid = uuid.UUID(agent_id) if agent_id else None
    tt = TriggerType(trigger_type) if trigger_type else None

    triggers = service.list_triggers(agent_id=agent_uuid, trigger_type=tt, active_only=active_only, limit=limit)
    return [_trigger_to_dict(t) for t in triggers]


@router.post("/")
async def create_trigger(
    request: CreateTriggerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService
    from app.models.agent_trigger import TriggerType

    service = TriggerService(db)
    try:
        trigger_type = TriggerType(request.trigger_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid trigger type: {request.trigger_type}")

    try:
        trigger = service.create_trigger(
            agent_id=uuid.UUID(request.agent_id),
            trigger_type=trigger_type,
            payload=request.payload,
            source_event_type=request.source_event_type,
            source_event_id=request.source_event_id,
            match_integration=request.match_integration,
            match_event_type=request.match_event_type,
            match_room_id=uuid.UUID(request.match_room_id) if request.match_room_id else None,
            schedule_interval_seconds=request.schedule_interval_seconds,
            cooldown_seconds=request.cooldown_seconds,
        )
        return _trigger_to_dict(trigger)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{trigger_id}")
async def get_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService

    service = TriggerService(db)
    trigger = service.get_trigger(uuid.UUID(trigger_id))
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _trigger_to_dict(trigger)


@router.put("/{trigger_id}")
async def update_trigger(
    trigger_id: str,
    request: UpdateTriggerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService

    service = TriggerService(db)
    updates = {}
    if request.is_active is not None:
        updates["is_active"] = request.is_active
    if request.cooldown_seconds is not None:
        updates["cooldown_seconds"] = request.cooldown_seconds
    if request.schedule_interval_seconds is not None:
        updates["schedule_interval_seconds"] = request.schedule_interval_seconds
    if request.payload is not None:
        updates["payload"] = request.payload

    trigger = service.update_trigger(uuid.UUID(trigger_id), **updates)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _trigger_to_dict(trigger)


@router.delete("/{trigger_id}")
async def delete_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService

    service = TriggerService(db)
    deleted = service.delete_trigger(uuid.UUID(trigger_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"success": True, "message": "Trigger deleted"}


@router.post("/{trigger_id}/activate")
async def activate_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService

    service = TriggerService(db)
    trigger = service.activate_trigger(uuid.UUID(trigger_id))
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _trigger_to_dict(trigger)


@router.post("/{trigger_id}/deactivate")
async def deactivate_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService

    service = TriggerService(db)
    trigger = service.deactivate_trigger(uuid.UUID(trigger_id))
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _trigger_to_dict(trigger)


# ------------------------------------------------------------------
# Fire trigger
# ------------------------------------------------------------------

@router.post("/fire")
async def fire_manual_trigger(
    request: ManualTriggerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create and immediately queue a manual trigger for an agent."""
    from app.services.trigger_service import TriggerService

    service = TriggerService(db)
    try:
        trigger = service.fire_manual_trigger(
            agent_id=uuid.UUID(request.agent_id),
            instruction=request.instruction,
            payload=request.payload,
        )
        return _trigger_to_dict(trigger)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------
# Execution history
# ------------------------------------------------------------------

@router.get("/{trigger_id}/executions")
async def get_trigger_executions(
    trigger_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService

    service = TriggerService(db)
    executions = service.get_executions(trigger_id=uuid.UUID(trigger_id), limit=limit)
    return [_execution_to_dict(e) for e in executions]


@router.get("/executions/all")
async def get_all_executions(
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.trigger_service import TriggerService

    service = TriggerService(db)
    agent_uuid = uuid.UUID(agent_id) if agent_id else None
    executions = service.get_executions(agent_id=agent_uuid, limit=limit)
    return [_execution_to_dict(e) for e in executions]


# ------------------------------------------------------------------
# Runtime status
# ------------------------------------------------------------------

@router.get("/runtime/status")
async def get_runtime_status(
    current_user: User = Depends(get_current_active_user),
):
    from app.services.agent_runtime import agent_runtime
    return agent_runtime.get_status()


@router.post("/runtime/agents/{agent_id}/activate")
async def activate_agent_runtime(
    agent_id: str,
    current_user: User = Depends(get_current_active_user),
):
    from app.services.agent_runtime import agent_runtime

    if not agent_runtime.is_running:
        raise HTTPException(status_code=503, detail="Agent runtime is not running")

    started = await agent_runtime.activate_agent(agent_id)
    return {
        "success": True,
        "agent_id": agent_id,
        "already_running": not started,
    }


@router.post("/runtime/agents/{agent_id}/deactivate")
async def deactivate_agent_runtime(
    agent_id: str,
    current_user: User = Depends(get_current_active_user),
):
    from app.services.agent_runtime import agent_runtime

    if not agent_runtime.is_running:
        raise HTTPException(status_code=503, detail="Agent runtime is not running")

    stopped = await agent_runtime.deactivate_agent(agent_id)
    return {
        "success": True,
        "agent_id": agent_id,
        "was_running": stopped,
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _trigger_to_dict(trigger) -> dict:
    return {
        "id": str(trigger.id),
        "agent_id": str(trigger.agent_id),
        "trigger_type": trigger.trigger_type.value,
        "status": trigger.status.value,
        "source_event_type": trigger.source_event_type,
        "source_event_id": trigger.source_event_id,
        "payload": trigger.payload,
        "schedule_cron": trigger.schedule_cron,
        "schedule_interval_seconds": trigger.schedule_interval_seconds,
        "next_run_at": trigger.next_run_at.isoformat() if trigger.next_run_at else None,
        "last_run_at": trigger.last_run_at.isoformat() if trigger.last_run_at else None,
        "match_integration": trigger.match_integration,
        "match_event_type": trigger.match_event_type,
        "match_room_id": str(trigger.match_room_id) if trigger.match_room_id else None,
        "is_active": trigger.is_active,
        "cooldown_seconds": trigger.cooldown_seconds,
        "max_retries": trigger.max_retries,
        "total_executions": trigger.total_executions,
        "last_execution_id": str(trigger.last_execution_id) if trigger.last_execution_id else None,
        "last_error": trigger.last_error,
        "created_at": trigger.created_at.isoformat() if trigger.created_at else None,
        "updated_at": trigger.updated_at.isoformat() if trigger.updated_at else None,
    }


def _execution_to_dict(execution) -> dict:
    return {
        "id": str(execution.id),
        "trigger_id": str(execution.trigger_id),
        "agent_id": str(execution.agent_id),
        "status": execution.status.value,
        "llm_reasoning": execution.llm_reasoning,
        "selected_tool": execution.selected_tool,
        "selected_action": execution.selected_action,
        "tool_parameters": execution.tool_parameters,
        "result": execution.result,
        "error_message": execution.error_message,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "duration_ms": execution.duration_ms,
        "trigger_type": execution.trigger_type,
        "source_event_type": execution.source_event_type,
        "source_event_id": execution.source_event_id,
        "created_at": execution.created_at.isoformat() if execution.created_at else None,
    }
