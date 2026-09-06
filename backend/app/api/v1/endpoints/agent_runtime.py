"""Agent Runtime API — status, manual triggers, and control."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.database.session import get_db
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class TriggerRequest(BaseModel):
    agent_id: str
    trigger_type: str = "manual"
    instruction: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


@router.get("/status")
async def get_runtime_status(current_user: User = Depends(get_current_active_user)):
    """Get the current status of the agent runtime."""
    from app.services.agent_runtime import agent_runtime
    return agent_runtime.get_status()


@router.get("/scheduler")
async def get_scheduler_status(current_user: User = Depends(get_current_active_user)):
    """Get the current status of the scheduler and all registered jobs."""
    from app.services.scheduler import scheduler
    return scheduler.get_status()


@router.post("/trigger")
async def trigger_agent(
    request: TriggerRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Manually trigger an agent to perform work."""
    from app.services.agent_runtime import agent_runtime, AgentTrigger, TriggerType

    if not agent_runtime.is_running:
        raise HTTPException(status_code=503, detail="Agent runtime is not running")

    try:
        trigger_type = TriggerType(request.trigger_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid trigger type: {request.trigger_type}")

    trigger = AgentTrigger(
        trigger_id=str(uuid.uuid4()),
        agent_id=request.agent_id,
        trigger_type=trigger_type,
        payload=request.payload or {},
    )

    if request.instruction:
        trigger.payload["instruction"] = request.instruction

    success = agent_runtime.trigger_agent(request.agent_id, trigger)
    if not success:
        raise HTTPException(status_code=404, detail="Agent loop not running or not found")

    return {
        "success": True,
        "trigger_id": trigger.trigger_id,
        "agent_id": request.agent_id,
        "message": f"Trigger queued for agent",
    }


@router.post("/agents/{agent_id}/activate")
async def activate_agent_runtime(
    agent_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Manually activate an agent in the runtime."""
    from app.services.agent_runtime import agent_runtime

    if not agent_runtime.is_running:
        raise HTTPException(status_code=503, detail="Agent runtime is not running")

    started = await agent_runtime.activate_agent(agent_id)
    return {
        "success": True,
        "agent_id": agent_id,
        "already_running": not started,
        "message": "Agent activated" if started else "Agent loop already running",
    }


@router.post("/agents/{agent_id}/deactivate")
async def deactivate_agent_runtime(
    agent_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Manually deactivate an agent in the runtime."""
    from app.services.agent_runtime import agent_runtime

    if not agent_runtime.is_running:
        raise HTTPException(status_code=503, detail="Agent runtime is not running")

    stopped = await agent_runtime.deactivate_agent(agent_id)
    return {
        "success": True,
        "agent_id": agent_id,
        "was_running": stopped,
        "message": "Agent deactivated" if stopped else "Agent loop was not running",
    }
