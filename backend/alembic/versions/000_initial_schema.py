"""Consolidated initial schema - all 27 tables

Revision ID: 000
Revises:
Create Date: 2026-08-27

This migration replaces the entire broken migration chain (001 through 0023)
with a single clean migration that creates the exact schema matching all
current SQLAlchemy models.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '000'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. users ─────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('google_id', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('role', sa.Enum('ceo', 'admin', 'user', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_unique_constraint('uq_users_google_id', 'users', ['google_id'])

    # ── 2. office_rooms ──────────────────────────────────────────────────
    op.create_table(
        'office_rooms',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('available', 'occupied', 'maintenance', name='roomstatus'), nullable=False),
        sa.Column('room_type', sa.String(), nullable=True),
        sa.Column('capacity', sa.String(), nullable=True, server_default='1'),
        sa.Column('visual_status', sa.Enum('offline', 'online_inactive', 'online_active', 'needs_attention', 'error', name='roomvisualstatus'), nullable=False, server_default='offline'),
        sa.Column('current_agent_id', sa.String(), nullable=True),
        sa.Column('current_user_id', sa.String(), nullable=True),
        sa.Column('room_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 3. agent_templates ───────────────────────────────────────────────
    op.create_table(
        'agent_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('default_goals', sa.JSON(), nullable=True),
        sa.Column('default_rules', sa.JSON(), nullable=True),
        sa.Column('default_permissions', sa.JSON(), nullable=True),
        sa.Column('default_tools', sa.JSON(), nullable=True),
        sa.Column('default_knowledge', sa.JSON(), nullable=True),
        sa.Column('icon_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 4. integrations ──────────────────────────────────────────────────
    op.create_table(
        'integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon_url', sa.String(500), nullable=True),
        sa.Column('auth_type', sa.String(50), nullable=False),
        sa.Column('config_schema', sa.JSON(), nullable=True),
        sa.Column('capabilities', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('oauth2_authorize_url', sa.String(500), nullable=True),
        sa.Column('oauth2_token_url', sa.String(500), nullable=True),
        sa.Column('oauth2_client_id_key', sa.String(100), nullable=True),
        sa.Column('oauth2_client_secret_key', sa.String(100), nullable=True),
        sa.Column('oauth2_scopes', sa.Text(), nullable=True),
        sa.Column('oauth2_redirect_path', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 5. ai_agents ─────────────────────────────────────────────────────
    op.create_table(
        'ai_agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'busy', name='agentstatus'), nullable=False),
        sa.Column('room_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('office_rooms.id'), nullable=True),
        sa.Column('goals', sa.String(), nullable=True),
        sa.Column('rules', sa.String(), nullable=True),
        sa.Column('permissions', sa.String(), nullable=True),
        sa.Column('tools', sa.String(), nullable=True),
        sa.Column('memory_settings', sa.String(), nullable=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agent_templates.id'), nullable=True),
        sa.Column('lifecycle_status', sa.Enum('draft', 'active', 'paused', 'inactive', 'error', 'disabled', 'archived', name='lifecyclestatus'), nullable=False, server_default='draft'),
        sa.Column('hired_at', sa.String(), nullable=True),
        sa.Column('last_active_at', sa.String(), nullable=True),
        sa.Column('paused_at', sa.String(), nullable=True),
        sa.Column('disabled_at', sa.String(), nullable=True),
        sa.Column('disabled_reason', sa.Text(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('archived_at', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 6. integration_accounts ──────────────────────────────────────────
    op.create_table(
        'integration_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('integration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('integrations.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=True),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('credentials', sa.JSON(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='connected'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_sync_at', sa.String(), nullable=True),
        sa.Column('oauth2_access_token', sa.Text(), nullable=True),
        sa.Column('oauth2_refresh_token', sa.Text(), nullable=True),
        sa.Column('oauth2_token_expiry', sa.String(), nullable=True),
        sa.Column('oauth2_scope', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'integration_id', name='uq_user_integration'),
    )

    # ── 7. agent_tools ───────────────────────────────────────────────────
    op.create_table(
        'agent_tools',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False, server_default='general'),
        sa.Column('integration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('integrations.id'), nullable=True),
        sa.Column('input_schema', sa.JSON(), nullable=True),
        sa.Column('output_schema', sa.JSON(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False, server_default='low'),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('version', sa.String(20), nullable=False, server_default='1.0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 8. permissions ───────────────────────────────────────────────────
    op.create_table(
        'permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('risk_level', sa.String(20), nullable=False, server_default='low'),
        sa.Column('default_status', sa.String(20), nullable=False, server_default='allowed'),
        sa.Column('default_approval_required', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('name', name='uq_permission_name'),
    )

    # ── 9. agent_permissions ─────────────────────────────────────────────
    op.create_table(
        'agent_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('permissions.id'), nullable=False),
        sa.Column('access_level', sa.String(20), nullable=False, server_default='allowed'),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('granted_by', sa.String(100), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('agent_id', 'permission_id', name='uq_agent_permission'),
    )

    # ── 10. knowledge_sources ────────────────────────────────────────────
    op.create_table(
        'knowledge_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False, server_default='general'),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('source_type', sa.String(20), nullable=False, server_default='note'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('chunk_count', sa.String(10), nullable=True, server_default='0'),
        sa.Column('embedding_id', sa.String(100), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 11. notifications ────────────────────────────────────────────────
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('priority', sa.String(20), nullable=False, server_default='low'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 12. audit_logs ──────────────────────────────────────────────────
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 13. email_accounts ──────────────────────────────────────────────
    op.create_table(
        'email_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('email_address', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('imap_host', sa.String(), nullable=False),
        sa.Column('imap_port', sa.Integer(), nullable=False, server_default='993'),
        sa.Column('imap_username', sa.String(), nullable=False),
        sa.Column('imap_password', sa.String(), nullable=False),
        sa.Column('imap_use_ssl', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('smtp_host', sa.String(), nullable=False),
        sa.Column('smtp_port', sa.Integer(), nullable=False, server_default='587'),
        sa.Column('smtp_username', sa.String(), nullable=False),
        sa.Column('smtp_password', sa.String(), nullable=False),
        sa.Column('smtp_use_ssl', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_sync_at', sa.String(), nullable=True),
        sa.Column('sync_error', sa.String(), nullable=True),
        sa.Column('sync_frequency_minutes', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 14. email_messages ───────────────────────────────────────────────
    op.create_table(
        'email_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('from_address', sa.String(), nullable=False),
        sa.Column('to_address', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('new', 'processing', 'replied', 'escalated', 'failed', name='emailstatus'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=True),
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.Column('draft_response', sa.Text(), nullable=True),
        sa.Column('category', sa.String(), nullable=True, server_default='general'),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('email_accounts.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 15. agent_tool_assignments ───────────────────────────────────────
    op.create_table(
        'agent_tool_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agent_tools.id'), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 16. tool_actions ─────────────────────────────────────────────────
    op.create_table(
        'tool_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agent_tools.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False, server_default='low'),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('input_schema', sa.JSON(), nullable=True),
        sa.Column('output_schema', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 17. tool_permissions ─────────────────────────────────────────────
    op.create_table(
        'tool_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agent_tools.id'), nullable=False),
        sa.Column('action_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tool_actions.id'), nullable=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('permissions.id'), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 18. risk_rules ───────────────────────────────────────────────────
    op.create_table(
        'risk_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('action_name', sa.String(100), nullable=True),
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agent_tools.id'), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('conditions', postgresql.JSON(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_risk_rules_action_name', 'risk_rules', ['action_name'])
    op.create_index('ix_risk_rules_tool_id', 'risk_rules', ['tool_id'])
    op.create_index('ix_risk_rules_is_active', 'risk_rules', ['is_active'])

    # ── 19. agent_knowledge_access ───────────────────────────────────────
    op.create_table(
        'agent_knowledge_access',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('knowledge_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('knowledge_sources.id'), nullable=False),
        sa.Column('access_level', sa.String(20), nullable=False, server_default='read'),
        sa.Column('granted_by', sa.String(50), nullable=True, server_default='system'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 20. approvals ────────────────────────────────────────────────────
    # task_id FK is added after tasks table is created (circular dependency).
    op.create_table(
        'approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agent_tools.id'), nullable=True),
        sa.Column('target', sa.String(255), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False, server_default='low'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('requested_at', sa.String(), nullable=True),
        sa.Column('decided_at', sa.String(), nullable=True),
        sa.Column('decided_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('decision_notes', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 21. tasks ────────────────────────────────────────────────────────
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'waiting_approval', 'completed', 'failed', 'cancelled', name='taskstatus'), nullable=False),
        sa.Column('task_type', sa.Enum('tool_execution', 'agent_collaboration', 'approval_required', 'general', name='tasktype'), nullable=False, server_default='general'),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('assigned_to_agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('priority', sa.Enum('low', 'medium', 'high', 'urgent', name='taskpriority'), nullable=False, server_default='medium'),
        sa.Column('started_at', sa.String(), nullable=True),
        sa.Column('completed_at', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('input_json', sa.JSON(), nullable=True),
        sa.Column('output_json', sa.JSON(), nullable=True),
        sa.Column('parent_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id'), nullable=True),
        sa.Column('approval_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('approvals.id'), nullable=True),
        sa.Column('tool_name', sa.String(), nullable=True),
        sa.Column('tool_action', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Add FK from approvals.task_id -> tasks.id (breaks circular dependency)
    op.create_foreign_key('approvals_task_id_fkey', 'approvals', 'tasks', ['task_id'], ['id'])

    # ── 22. agent_activities ─────────────────────────────────────────────
    op.create_table(
        'agent_activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('activity_type', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id'), nullable=True),
        sa.Column('tool_name', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 23. task_events ──────────────────────────────────────────────────
    op.create_table(
        'task_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('old_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('performed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 24. approval_events ──────────────────────────────────────────────
    op.create_table(
        'approval_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('approval_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('approvals.id'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('old_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('performed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 25. agent_collaborations ─────────────────────────────────────────
    op.create_table(
        'agent_collaborations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('from_agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('to_agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id'), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # ── 26. agent_integrations ───────────────────────────────────────────
    op.create_table(
        'agent_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_agents.id'), nullable=False),
        sa.Column('integration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('integrations.id'), nullable=False),
        sa.Column('capabilities', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('agent_integrations')
    op.drop_table('agent_collaborations')
    op.drop_table('approval_events')
    op.drop_table('task_events')
    op.drop_table('agent_activities')
    op.drop_table('tasks')
    op.drop_table('approvals')
    op.drop_table('agent_knowledge_access')
    op.drop_index('ix_risk_rules_is_active', table_name='risk_rules')
    op.drop_index('ix_risk_rules_tool_id', table_name='risk_rules')
    op.drop_index('ix_risk_rules_action_name', table_name='risk_rules')
    op.drop_table('risk_rules')
    op.drop_table('tool_permissions')
    op.drop_table('tool_actions')
    op.drop_table('agent_tool_assignments')
    op.drop_table('email_messages')
    op.drop_table('email_accounts')
    op.drop_table('audit_logs')
    op.drop_table('notifications')
    op.drop_table('agent_permissions')
    op.drop_table('permissions')
    op.drop_table('agent_tools')
    op.drop_table('integration_accounts')
    op.drop_table('integrations')
    op.drop_table('agent_templates')
    op.drop_table('ai_agents')
    op.drop_table('office_rooms')
    op.drop_table('users')

    # Drop enum types
    sa.Enum(name='emailstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='lifecyclestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='tasktype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='taskpriority').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='taskstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='roomvisualstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='roomstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='agentstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
