from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID


class AgentSummary(BaseModel):
    id: UUID
    name: str
    role: str
    status: str
    room_name: Optional[str] = None


class TaskSummary(BaseModel):
    id: UUID
    title: str
    status: str
    priority: str
    agent_name: str
    created_at: str


class DashboardSummary(BaseModel):
    total_agents: int
    active_agents: int
    busy_agents: int
    inactive_agents: int

    total_rooms: int
    available_rooms: int
    occupied_rooms: int
    maintenance_rooms: int

    total_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    failed_tasks: int

    agents: List[AgentSummary]
    recent_tasks: List[TaskSummary]
    pending_actions: List[TaskSummary]
