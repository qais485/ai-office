from fastapi import APIRouter

from app.api.v1.endpoints import (
    health, auth, agents, rooms, tasks, dashboard, emails, activity, email_accounts,
    templates, integrations, tools, permissions, approvals, knowledge, notifications, audit,
    hiring, tool_execution, ceo_dashboard, ceo_inbox, agent_collaboration, websocket, analytics,
    risk_rules, agent_runtime, triggers, gmail_monitor, gmail_push
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(emails.router, prefix="/emails", tags=["emails"])
api_router.include_router(activity.router, prefix="/activity", tags=["activity"])
api_router.include_router(email_accounts.router, prefix="/email-accounts", tags=["email-accounts"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["permissions"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(hiring.router, prefix="/hiring", tags=["hiring"])
api_router.include_router(tool_execution.router, prefix="/tool-execution", tags=["tool-execution"])
api_router.include_router(ceo_dashboard.router, prefix="/ceo/dashboard", tags=["ceo-dashboard"])
api_router.include_router(ceo_inbox.router, prefix="/ceo/inbox", tags=["ceo-inbox"])
api_router.include_router(agent_collaboration.router, prefix="/collaboration", tags=["agent-collaboration"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(risk_rules.router, prefix="/risk-rules", tags=["risk-rules"])
api_router.include_router(agent_runtime.router, prefix="/runtime", tags=["agent-runtime"])
api_router.include_router(triggers.router, prefix="/triggers", tags=["triggers"])
api_router.include_router(gmail_monitor.router, prefix="/gmail-monitor", tags=["gmail-monitor"])
api_router.include_router(gmail_push.router, prefix="/gmail-push", tags=["gmail-push"])
