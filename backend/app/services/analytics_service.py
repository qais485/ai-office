from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.agent import AIAgent
from app.models.task import Task
from app.models.activity import AgentActivity
from app.models.approval import Approval
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_agent_performance(self, agent_id: UUID, days: int = 30) -> Dict:
        logger.debug("Getting agent performance: agent=%s days=%d", agent_id, days)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        tasks_completed = self.db.query(func.count(Task.id)).filter(
            and_(
                Task.assigned_agent_id == agent_id,
                Task.status == "completed",
                Task.completed_at >= start_date
            )
        ).scalar() or 0
        
        tasks_failed = self.db.query(func.count(Task.id)).filter(
            and_(
                Task.assigned_agent_id == agent_id,
                Task.status == "failed",
                Task.completed_at >= start_date
            )
        ).scalar() or 0
        
        total_tasks = tasks_completed + tasks_failed
        success_rate = (tasks_completed / total_tasks * 100) if total_tasks > 0 else 0
        
        avg_duration = self.db.query(
            func.avg(
                func.extract('epoch', Task.completed_at) - func.extract('epoch', Task.created_at)
            )
        ).filter(
            and_(
                Task.assigned_agent_id == agent_id,
                Task.status == "completed",
                Task.completed_at >= start_date
            )
        ).scalar() or 0
        
        activities_count = self.db.query(func.count(AgentActivity.id)).filter(
            and_(
                AgentActivity.agent_id == agent_id,
                AgentActivity.created_at >= start_date
            )
        ).scalar() or 0
        
        approvals_pending = self.db.query(func.count(Approval.id)).filter(
            and_(
                Approval.agent_id == agent_id,
                Approval.status == "pending"
            )
        ).scalar() or 0
        
        return {
            "agent_id": str(agent_id),
            "period_days": days,
            "tasks_completed": tasks_completed,
            "tasks_failed": tasks_failed,
            "success_rate": round(success_rate, 2),
            "avg_duration_seconds": round(avg_duration, 2),
            "activities_count": activities_count,
            "approvals_pending": approvals_pending
        }
    
    def get_company_analytics(self, days: int = 30) -> Dict:
        logger.debug("Getting company analytics: days=%d", days)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        total_agents = self.db.query(func.count(AIAgent.id)).filter(
            AIAgent.lifecycle_status == "active"
        ).scalar() or 0
        
        total_tasks_completed = self.db.query(func.count(Task.id)).filter(
            and_(
                Task.status == "completed",
                Task.completed_at >= start_date
            )
        ).scalar() or 0
        
        total_tasks_failed = self.db.query(func.count(Task.id)).filter(
            and_(
                Task.status == "failed",
                Task.completed_at >= start_date
            )
        ).scalar() or 0
        
        total_activities = self.db.query(func.count(AgentActivity.id)).filter(
            AgentActivity.created_at >= start_date
        ).scalar() or 0
        
        pending_approvals = self.db.query(func.count(Approval.id)).filter(
            Approval.status == "pending"
        ).scalar() or 0
        
        return {
            "period_days": days,
            "total_agents": total_agents,
            "total_tasks_completed": total_tasks_completed,
            "total_tasks_failed": total_tasks_failed,
            "success_rate": round((total_tasks_completed / (total_tasks_completed + total_tasks_failed) * 100) if (total_tasks_completed + total_tasks_failed) > 0 else 0, 2),
            "total_activities": total_activities,
            "pending_approvals": pending_approvals
        }
    
    def get_agent_ranking(self, days: int = 30) -> List[Dict]:
        logger.debug("Getting agent ranking: days=%d", days)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        agents = self.db.query(AIAgent).filter(AIAgent.lifecycle_status == "active").all()
        
        rankings = []
        for agent in agents:
            tasks_completed = self.db.query(func.count(Task.id)).filter(
                and_(
                    Task.assigned_agent_id == agent.id,
                    Task.status == "completed",
                    Task.completed_at >= start_date
                )
            ).scalar() or 0
            
            tasks_failed = self.db.query(func.count(Task.id)).filter(
                and_(
                    Task.assigned_agent_id == agent.id,
                    Task.status == "failed",
                    Task.completed_at >= start_date
                )
            ).scalar() or 0
            
            total_tasks = tasks_completed + tasks_failed
            success_rate = (tasks_completed / total_tasks * 100) if total_tasks > 0 else 0
            
            rankings.append({
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "tasks_completed": tasks_completed,
                "success_rate": round(success_rate, 2)
            })
        
        rankings.sort(key=lambda x: x["tasks_completed"], reverse=True)
        
        return rankings
    
    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        logger.debug("Getting daily stats: days=%d", days)
        stats = []
        
        for i in range(days):
            date = datetime.now(timezone.utc) - timedelta(days=i)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            tasks_completed = self.db.query(func.count(Task.id)).filter(
                and_(
                    Task.status == "completed",
                    Task.completed_at >= start_of_day,
                    Task.completed_at < end_of_day
                )
            ).scalar() or 0
            
            tasks_failed = self.db.query(func.count(Task.id)).filter(
                and_(
                    Task.status == "failed",
                    Task.completed_at >= start_of_day,
                    Task.completed_at < end_of_day
                )
            ).scalar() or 0
            
            activities_count = self.db.query(func.count(AgentActivity.id)).filter(
                and_(
                    AgentActivity.created_at >= start_of_day,
                    AgentActivity.created_at < end_of_day
                )
            ).scalar() or 0
            
            stats.append({
                "date": start_of_day.date().isoformat(),
                "tasks_completed": tasks_completed,
                "tasks_failed": tasks_failed,
                "activities_count": activities_count
            })
        
        return list(reversed(stats))
