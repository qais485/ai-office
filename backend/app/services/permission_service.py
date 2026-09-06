from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.permission import Permission
from app.models.agent_permission import AgentPermission
from app.models.agent import AIAgent
from app.schemas.permission import PermissionCreate, PermissionUpdate, AgentPermissionCreate, AgentPermissionUpdate
import logging

logger = logging.getLogger(__name__)


class PermissionService:
    def __init__(self, db: Session):
        self.db = db

    def get_permissions(self, active_only: bool = False, category: Optional[str] = None) -> List[Permission]:
        query = self.db.query(Permission)
        if active_only:
            query = query.filter(Permission.is_active == True)
        if category:
            query = query.filter(Permission.category == category)
        return query.all()

    def get_permission(self, permission_id: UUID) -> Optional[Permission]:
        return self.db.query(Permission).filter(Permission.id == permission_id).first()

    def get_permission_by_name(self, name: str) -> Optional[Permission]:
        return self.db.query(Permission).filter(Permission.name == name).first()

    def create_permission(self, data: PermissionCreate) -> Permission:
        permission = Permission(**data.model_dump())
        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def update_permission(self, permission_id: UUID, data: PermissionUpdate) -> Optional[Permission]:
        permission = self.get_permission(permission_id)
        if permission:
            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(permission, key, value)
            self.db.commit()
            self.db.refresh(permission)
        return permission

    def delete_permission(self, permission_id: UUID) -> bool:
        permission = self.get_permission(permission_id)
        if permission:
            self.db.delete(permission)
            self.db.commit()
            return True
        return False

    def get_permissions_by_category(self, category: str) -> List[Permission]:
        return self.db.query(Permission).filter(
            Permission.category == category,
            Permission.is_active == True
        ).all()

    def get_permission_categories(self) -> List[str]:
        from sqlalchemy import distinct
        categories = self.db.query(distinct(Permission.category)).all()
        return [c[0] for c in categories]

    def get_agent_permissions(self, agent_id: UUID) -> List[AgentPermission]:
        return self.db.query(AgentPermission).filter(AgentPermission.agent_id == agent_id).all()

    def get_agent_permissions_with_details(self, agent_id: UUID) -> List[dict]:
        agent_perms = self.db.query(AgentPermission).filter(AgentPermission.agent_id == agent_id).all()
        result = []
        for ap in agent_perms:
            perm = self.db.query(Permission).filter(Permission.id == ap.permission_id).first()
            if perm:
                result.append({
                    "id": ap.id,
                    "agent_id": ap.agent_id,
                    "permission_id": ap.permission_id,
                    "access_level": ap.access_level,
                    "conditions": ap.conditions,
                    "granted_by": ap.granted_by,
                    "notes": ap.notes,
                    "created_at": ap.created_at,
                    "updated_at": ap.updated_at,
                    "permission_name": perm.name,
                    "permission_description": perm.description,
                    "permission_category": perm.category,
                    "permission_risk_level": perm.risk_level
                })
        return result

    def set_agent_permission(self, agent_id: UUID, data: AgentPermissionCreate, granted_by: Optional[str] = None) -> AgentPermission:
        logger.info("Setting permission for agent=%s perm=%s", agent_id, data.permission_id)
        existing = self.db.query(AgentPermission).filter(
            AgentPermission.agent_id == agent_id,
            AgentPermission.permission_id == data.permission_id
        ).first()
        
        if existing:
            existing.access_level = data.access_level
            existing.conditions = data.conditions
            existing.notes = data.notes
            if granted_by:
                existing.granted_by = granted_by
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        agent_perm = AgentPermission(
            agent_id=agent_id,
            permission_id=data.permission_id,
            access_level=data.access_level,
            conditions=data.conditions,
            granted_by=granted_by,
            notes=data.notes
        )
        self.db.add(agent_perm)
        self.db.commit()
        self.db.refresh(agent_perm)
        return agent_perm

    def set_agent_permissions_batch(self, agent_id: UUID, permissions: List[dict], granted_by: Optional[str] = None) -> List[AgentPermission]:
        results = []
        for perm_data in permissions:
            permission = self.get_permission_by_name(perm_data["name"])
            if not permission:
                continue
            
            access_level = perm_data.get("access_level", permission.default_status)
            notes = perm_data.get("notes")
            
            data = AgentPermissionCreate(
                permission_id=permission.id,
                access_level=access_level,
                notes=notes
            )
            result = self.set_agent_permission(agent_id, data, granted_by)
            results.append(result)
        return results

    def check_permission(self, agent_id: UUID, permission_name: str) -> Tuple[bool, str, str]:
        logger.debug("Checking permission: agent=%s perm=%s", agent_id, permission_name)
        permission = self.get_permission_by_name(permission_name)
        if not permission:
            return False, "denied", f"Permission '{permission_name}' not found"
        
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return False, "denied", "Agent not found"
        
        if agent.lifecycle_status.value != "active":
            return False, "denied", f"Agent is not active (status: {agent.lifecycle_status.value})"
        
        agent_perm = self.db.query(AgentPermission).filter(
            AgentPermission.agent_id == agent_id,
            AgentPermission.permission_id == permission.id
        ).first()
        
        if not agent_perm:
            return False, "denied", f"Permission '{permission_name}' not granted to agent"
        
        if agent_perm.access_level == "denied":
            return False, "denied", f"Permission '{permission_name}' is explicitly denied"
        
        if agent_perm.access_level == "approval_required":
            return True, "approval_required", f"Permission '{permission_name}' requires approval"
        
        return True, "allowed", f"Permission '{permission_name}' granted"

    def check_permissions_batch(self, agent_id: UUID, permission_names: List[str]) -> dict:
        results = {}
        for name in permission_names:
            has_perm, access_level, message = self.check_permission(agent_id, name)
            results[name] = {
                "has_permission": has_perm,
                "access_level": access_level,
                "message": message,
                "requires_approval": access_level == "approval_required"
            }
        return results

    def delete_agent_permission(self, agent_id: UUID, permission_id: UUID) -> bool:
        agent_perm = self.db.query(AgentPermission).filter(
            AgentPermission.agent_id == agent_id,
            AgentPermission.permission_id == permission_id
        ).first()
        
        if agent_perm:
            self.db.delete(agent_perm)
            self.db.commit()
            return True
        return False

    def revoke_all_agent_permissions(self, agent_id: UUID) -> bool:
        self.db.query(AgentPermission).filter(AgentPermission.agent_id == agent_id).delete()
        self.db.commit()
        return True

    def get_agents_with_permission(self, permission_name: str) -> List[dict]:
        from app.models.agent import AIAgent
        permission = self.get_permission_by_name(permission_name)
        if not permission:
            return []
        
        agent_perms = self.db.query(AgentPermission).filter(
            AgentPermission.permission_id == permission.id,
            AgentPermission.access_level != "denied"
        ).all()
        
        if not agent_perms:
            return []
        
        agent_ids = [ap.agent_id for ap in agent_perms]
        agents = self.db.query(AIAgent).filter(AIAgent.id.in_(agent_ids)).all()
        return [{"id": str(a.id), "name": a.name, "role": a.role} for a in agents]
