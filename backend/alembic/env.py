import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Ensure the backend directory is on sys.path so `app.*` imports work
# regardless of where alembic is invoked from.
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with DATABASE_URL from .env (via pydantic-settings)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.models.base import Base
from app.models.user import User
from app.models.agent import AIAgent
from app.models.room import OfficeRoom
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.email import EmailMessage
from app.models.email_account import EmailAccount
from app.models.activity import AgentActivity
from app.models.template import AgentTemplate
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.models.tool_permission import ToolPermission
from app.models.agent_tool_assignment import AgentToolAssignment
from app.models.permission import Permission
from app.models.agent_permission import AgentPermission
from app.models.approval import Approval
from app.models.approval_event import ApprovalEvent
from app.models.knowledge import KnowledgeSource
from app.models.agent_knowledge import AgentKnowledgeAccess
from app.models.agent_collaboration import AgentCollaboration
from app.models.agent_integration import AgentIntegration
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.risk_rule import RiskRule

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
