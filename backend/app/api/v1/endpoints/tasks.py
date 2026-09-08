from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.services.task_service import TaskService
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.agent import AIAgent

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _enrich_task(task, db: Session) -> dict:
    """Single-task enrich (delegates to batch version — one query)."""
    return _enrich_tasks([task], db)[0]


def _enrich_tasks(tasks: list, db: Session) -> list[dict]:
    """Batch-enrich tasks with agent names in ONE query (avoids N+1)."""
    data = [TaskResponse.model_validate(t).model_dump() for t in tasks]
    agent_ids = {t.agent_id for t in tasks if t.agent_id}
    agent_names: dict = {}
    if agent_ids:
        agents = db.query(AIAgent).filter(AIAgent.id.in_(agent_ids)).all()
        agent_names = {a.id: a.name for a in agents}
    for item, task in zip(data, tasks):
        item["agent_name"] = agent_names.get(task.agent_id)
    return data


@router.get("/", response_model=list[TaskResponse])
def get_tasks(
    agent_id: Optional[UUID] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    task_service = TaskService(db)
    tasks = task_service.get_tasks(agent_id=agent_id, status=status, priority=priority, task_type=task_type, limit=limit)
    logger.debug("Listed %d tasks", len(tasks))
    return _enrich_tasks(tasks, db)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    logger.debug("Retrieved task %s", task_id)
    return _enrich_task(task, db)


@router.post("/", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    created = task_service.create_task(task)
    logger.info("Created task %s", created.id)
    return _enrich_task(created, db)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(task_id: UUID, task: TaskUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    updated = task_service.update_task(task_id, task)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info("Updated task %s", task_id)
    return _enrich_task(updated, db)


@router.delete("/{task_id}")
def delete_task(task_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    deleted = task_service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info("Deleted task %s", task_id)
    return {"detail": "Task deleted"}


@router.post("/{task_id}/start", response_model=TaskResponse)
def start_task(task_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    task = task_service.start_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or cannot be started")
    logger.info("Started task %s", task_id)
    return _enrich_task(task, db)


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(task_id: UUID, result: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    task = task_service.complete_task(task_id, result=result)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or cannot be completed")
    logger.info("Completed task %s", task_id)
    return _enrich_task(task, db)


@router.post("/{task_id}/fail", response_model=TaskResponse)
def fail_task(task_id: UUID, error_message: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    task = task_service.fail_task(task_id, error_message)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or cannot be failed")
    logger.info("Failed task %s: %s", task_id, error_message)
    return _enrich_task(task, db)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(task_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    task = task_service.cancel_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
    logger.info("Cancelled task %s", task_id)
    return _enrich_task(task, db)


@router.post("/{task_id}/handoff", response_model=TaskResponse)
def handoff_task(task_id: UUID, to_agent_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    task = task_service.handoff_task(task_id, to_agent_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or cannot be handed off")
    logger.info("Handed off task %s to agent %s", task_id, to_agent_id)
    return _enrich_task(task, db)


@router.get("/{task_id}/subtasks", response_model=list[TaskResponse])
def get_subtasks(task_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    subtasks = task_service.get_subtasks(task_id)
    return _enrich_tasks(subtasks, db)


@router.get("/stats/summary")
def get_task_stats(agent_id: Optional[UUID] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task_service = TaskService(db)
    return task_service.get_task_stats(agent_id=agent_id, user_id=current_user.id)
