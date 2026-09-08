import logging
from sqlalchemy.orm import Session

from app.models.template import AgentTemplate
from app.models.integration import Integration
from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.models.tool_permission import ToolPermission
from app.models.permission import Permission

logger = logging.getLogger(__name__)


def seed_templates(db: Session):
    templates = [
        {
            "name": "Email Support Agent",
            "role": "email_support",
            "description": "Handles customer email support, responds to inquiries, and escalates complex issues to the CEO.",
            "default_goals": [
                "Respond to customer emails professionally",
                "Resolve customer issues efficiently",
                "Maintain customer satisfaction",
                "Escalate complex issues to CEO when needed"
            ],
            "default_rules": [
                "Always be polite and professional",
                "Never make financial decisions without CEO approval",
                "Keep responses concise and helpful",
                "Log all interactions in memory"
            ],
            "default_permissions": ["read_emails", "write_emails", "create_tickets", "search_customers"],
            "default_tools": ["email_reader", "email_writer", "knowledge_base", "ticket_system"],
            "icon_url": "/icons/email-support.svg"
        },
        {
            "name": "Content Writer Agent",
            "role": "content_writer",
            "description": "Creates blog posts, social media content, and marketing materials.",
            "default_goals": [
                "Create engaging content",
                "Maintain brand voice",
                "Meet content deadlines",
                "Optimize for SEO"
            ],
            "default_rules": [
                "Follow brand guidelines",
                "Never publish without CEO approval",
                "Fact-check all content",
                "Maintain consistent tone"
            ],
            "default_permissions": ["write_content", "read_knowledge", "publish_content"],
            "default_tools": ["content_editor", "knowledge_base", "seo_analyzer"],
            "icon_url": "/icons/content-writer.svg"
        },
        {
            "name": "Social Media Manager",
            "role": "social_media",
            "description": "Manages social media accounts, creates posts, and engages with followers.",
            "default_goals": [
                "Grow social media presence",
                "Engage with followers",
                "Maintain brand consistency",
                "Track social media metrics"
            ],
            "default_rules": [
                "Never post without CEO approval",
                "Maintain professional tone",
                "Respond to comments promptly",
                "Avoid controversial topics"
            ],
            "default_permissions": ["read_social", "write_social", "schedule_posts"],
            "default_tools": ["social_media_manager", "analytics_tool"],
            "icon_url": "/icons/social-media.svg"
        },
        {
            "name": "Sales Agent",
            "role": "sales",
            "description": "Handles sales inquiries, follows up with leads, and closes deals.",
            "default_goals": [
                "Generate revenue",
                "Follow up with leads",
                "Close deals efficiently",
                "Maintain customer relationships"
            ],
            "default_rules": [
                "Never offer discounts without CEO approval",
                "Follow up within 24 hours",
                "Track all sales activities",
                "Escalate large deals to CEO"
            ],
            "default_permissions": ["read_leads", "write_leads", "send_proposals", "create_invoices"],
            "default_tools": ["crm_tool", "email_writer", "proposal_generator"],
            "icon_url": "/icons/sales.svg"
        },
        {
            "name": "Research Agent",
            "role": "research",
            "description": "Conducts research, analyzes data, and provides insights.",
            "default_goals": [
                "Conduct thorough research",
                "Provide actionable insights",
                "Maintain data accuracy",
                "Present findings clearly"
            ],
            "default_rules": [
                "Cite all sources",
                "Verify information before presenting",
                "Maintain objectivity",
                "Protect confidential information"
            ],
            "default_permissions": ["read_knowledge", "search_web", "analyze_data"],
            "default_tools": ["web_search", "data_analyzer", "report_generator"],
            "icon_url": "/icons/research.svg"
        },
        {
            "name": "Business Analyst",
            "role": "analyst",
            "description": "Analyzes business data, creates reports, and provides recommendations.",
            "default_goals": [
                "Analyze business metrics",
                "Identify trends and patterns",
                "Provide data-driven recommendations",
                "Create comprehensive reports"
            ],
            "default_rules": [
                "Base recommendations on data",
                "Maintain objectivity",
                "Protect sensitive data",
                "Present findings clearly"
            ],
            "default_permissions": ["read_analytics", "write_reports", "access_database"],
            "default_tools": ["analytics_tool", "report_generator", "database_query"],
            "icon_url": "/icons/analyst.svg"
        },
        {
            "name": "Executive Assistant",
            "role": "executive_assistant",
            "description": "Manages schedules, organizes meetings, and handles administrative tasks.",
            "default_goals": [
                "Manage CEO's schedule",
                "Organize meetings efficiently",
                "Handle administrative tasks",
                "Prioritize important communications"
            ],
            "default_rules": [
                "Always prioritize CEO's time",
                "Maintain confidentiality",
                "Be proactive in scheduling",
                "Escalate urgent matters immediately"
            ],
            "default_permissions": ["read_calendar", "write_calendar", "manage_emails", "schedule_meetings"],
            "default_tools": ["calendar_manager", "email_reader", "task_manager"],
            "icon_url": "/icons/executive-assistant.svg"
        },
        {
            "name": "Customer Support Agent",
            "role": "customer_support",
            "description": "Handles customer support tickets, resolves issues, and provides assistance.",
            "default_goals": [
                "Resolve customer issues quickly",
                "Maintain high satisfaction rates",
                "Escalate complex issues",
                "Document all interactions"
            ],
            "default_rules": [
                "Respond within SLA",
                "Be empathetic and professional",
                "Never make promises without approval",
                "Log all interactions"
            ],
            "default_permissions": ["read_tickets", "write_tickets", "access_knowledge_base"],
            "default_tools": ["ticket_system", "knowledge_base", "chat_tool"],
            "icon_url": "/icons/customer-support.svg"
        },
        {
            "name": "Telegram Support Agent",
            "role": "telegram_support",
            "description": "Handles customer conversations on Telegram — via the connected Telegram Bot (customer chat) and/or the connected Telegram user account (MTProto) — answers from the knowledge base, and escalates complex issues to the CEO.",
            "default_goals": [
                "Respond to Telegram customer messages professionally",
                "Answer customer questions from the company knowledge base",
                "Resolve customer issues efficiently",
                "Escalate complex issues to CEO when needed"
            ],
            "default_rules": [
                "Always be polite and professional",
                "Never make financial decisions without CEO approval",
                "Keep responses concise and helpful",
                "Respect Telegram rate limits and never spam users"
            ],
            "default_permissions": [
                "send_messages",
                "telegram_account_send",
                "telegram_account_read",
                "read_knowledge"
            ],
            "default_tools": [
                "telegram_messaging",
                "telegram_account_messaging",
                "knowledge_base"
            ],
            "icon_url": "/icons/telegram.svg"
        }
    ]

    for template_data in templates:
        existing = db.query(AgentTemplate).filter(AgentTemplate.name == template_data["name"]).first()
        if not existing:
            template = AgentTemplate(**template_data)
            db.add(template)
            logger.info(f"Created template: {template_data['name']}")

    # Backfill: keep the Telegram Support Agent template current on databases
    # where it already exists (seed_templates is create-if-missing, so template
    # upgrades would otherwise never reach them). Scoped to this one template.
    tg_support = db.query(AgentTemplate).filter(AgentTemplate.name == "Telegram Support Agent").first()
    if tg_support:
        target = next(t for t in templates if t["name"] == "Telegram Support Agent")
        for field in ("description", "default_goals", "default_rules", "default_permissions", "default_tools"):
            new_value = target[field]
            if getattr(tg_support, field) != new_value:
                setattr(tg_support, field, new_value)
                logger.info(f"Updated Telegram Support Agent template field: {field}")

    db.commit()


def seed_integrations(db: Session):
    integrations = [
        {
            "name": "gmail",
            "display_name": "Gmail",
            "description": "Google Gmail email service",
            "auth_type": "oauth2",
            "oauth2_authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "oauth2_token_url": "https://oauth2.googleapis.com/token",
            "oauth2_client_id_key": "GOOGLE_CLIENT_ID",
            "oauth2_client_secret_key": "GOOGLE_CLIENT_SECRET",
            "oauth2_scopes": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.modify",
            "oauth2_redirect_path": "/api/v1/integrations/oauth2/callback",
            "capabilities": {
                "read_emails": True,
                "send_emails": True,
                "search_emails": True,
                "create_drafts": True,
                "manage_labels": True
            },
            "icon_url": "/icons/gmail.svg"
        },
        {
            "name": "telegram",
            "display_name": "Telegram Bot",
            "description": "Telegram Bot API — send and receive messages through a bot token from @BotFather",
            "auth_type": "bot_token",
            "capabilities": {
                "send_messages": True,
                "receive_messages": True,
                "create_groups": True,
                "manage_channels": True
            },
            "icon_url": "/icons/telegram.svg"
        },
        {
            "name": "telegram_account",
            "display_name": "Telegram Account",
            "description": "Telegram user account — send and receive messages as yourself, using the API ID and API Hash from my.telegram.org",
            "auth_type": "api_id_hash",
            "capabilities": {
                "send_messages": True,
                "receive_messages": True,
                "read_history": True
            },
            "icon_url": "/icons/telegram.svg"
        },
        {
            "name": "instagram",
            "display_name": "Instagram",
            "description": "Instagram social media platform",
            "auth_type": "oauth2",
            "oauth2_authorize_url": "https://www.facebook.com/v21.0/dialog/oauth",
            "oauth2_token_url": "https://graph.facebook.com/v21.0/oauth/access_token",
            "oauth2_client_id_key": "INSTAGRAM_CLIENT_ID",
            "oauth2_client_secret_key": "INSTAGRAM_CLIENT_SECRET",
            # Facebook scopes are COMMA-separated. pages_show_list is REQUIRED
            # for /me/accounts to return the user's Pages (without it the list
            # is empty and no linked Instagram account can ever be found);
            # pages_read_engagement allows reading Page-level data. Page access
            # tokens are derived from these to call the Instagram Graph API.
            "oauth2_scopes": "pages_show_list,pages_read_engagement,instagram_basic,instagram_content_publish,instagram_manage_comments",
            "oauth2_redirect_path": "/api/v1/integrations/oauth2/callback",
            "capabilities": {
                "post_content": True,
                "manage_comments": True,
                "view_analytics": True,
                "story_management": True
            },
            "icon_url": "/icons/instagram.svg"
        },
        {
            "name": "slack",
            "display_name": "Slack",
            "description": "Slack team communication platform",
            "auth_type": "oauth2",
            "oauth2_authorize_url": "https://slack.com/oauth/v2/authorize",
            "oauth2_token_url": "https://slack.com/api/oauth.v2.access",
            "oauth2_client_id_key": "SLACK_CLIENT_ID",
            "oauth2_client_secret_key": "SLACK_CLIENT_SECRET",
            "oauth2_scopes": "chat:write channels:read channels:history im:write files:write",
            "oauth2_redirect_path": "/api/v1/integrations/oauth2/callback",
            "capabilities": {
                "send_messages": True,
                "read_messages": True,
                "manage_channels": True,
                "file_sharing": True
            },
            "icon_url": "/icons/slack.svg"
        },
        {
            "name": "discord",
            "display_name": "Discord",
            "description": "Discord communication platform",
            "auth_type": "bot_token",
            "capabilities": {
                "send_messages": True,
                "read_messages": True,
                "manage_servers": True,
                "voice_channels": True
            },
            "icon_url": "/icons/discord.svg"
        },
        {
            "name": "google_calendar",
            "display_name": "Google Calendar",
            "description": "Google Calendar scheduling service",
            "auth_type": "oauth2",
            "oauth2_authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "oauth2_token_url": "https://oauth2.googleapis.com/token",
            "oauth2_client_id_key": "GOOGLE_CLIENT_ID",
            "oauth2_client_secret_key": "GOOGLE_CLIENT_SECRET",
            "oauth2_scopes": "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events",
            "oauth2_redirect_path": "/api/v1/integrations/oauth2/callback",
            "capabilities": {
                "read_events": True,
                "create_events": True,
                "manage_events": True,
                "send_invites": True
            },
            "icon_url": "/icons/google-calendar.svg"
        },
        {
            "name": "google_drive",
            "display_name": "Google Drive",
            "description": "Google Drive file storage service",
            "auth_type": "oauth2",
            "oauth2_authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "oauth2_token_url": "https://oauth2.googleapis.com/token",
            "oauth2_client_id_key": "GOOGLE_CLIENT_ID",
            "oauth2_client_secret_key": "GOOGLE_CLIENT_SECRET",
            "oauth2_scopes": "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file",
            "oauth2_redirect_path": "/api/v1/integrations/oauth2/callback",
            "capabilities": {
                "read_files": True,
                "write_files": True,
                "share_files": True,
                "manage_folders": True
            },
            "icon_url": "/icons/google-drive.svg"
        },
        {
            "name": "notion",
            "display_name": "Notion",
            "description": "Notion workspace and documentation platform",
            "auth_type": "api_key",
            "capabilities": {
                "read_pages": True,
                "write_pages": True,
                "manage_databases": True,
                "search_content": True
            },
            "icon_url": "/icons/notion.svg"
        },
        {
            "name": "crm",
            "display_name": "CRM System",
            "description": "Customer Relationship Management system",
            "auth_type": "api_key",
            "capabilities": {
                "read_contacts": True,
                "write_contacts": True,
                "manage_deals": True,
                "track_interactions": True
            },
            "icon_url": "/icons/crm.svg"
        }
    ]

    for integration_data in integrations:
        existing = db.query(Integration).filter(Integration.name == integration_data["name"]).first()
        if not existing:
            integration = Integration(**integration_data)
            db.add(integration)
            logger.info(f"Created integration: {integration_data['name']}")
        else:
            # Update basic seed fields on existing integrations (keeps DB rows
            # in sync with renamed / re-typed definitions, e.g. telegram → bot)
            updated = False
            basic_fields = ["display_name", "description", "auth_type", "icon_url"]
            for field in basic_fields:
                new_val = integration_data.get(field)
                if new_val and getattr(existing, field) != new_val:
                    setattr(existing, field, new_val)
                    updated = True
            # Update OAuth2 fields on existing integrations
            oauth2_fields = ["oauth2_authorize_url", "oauth2_token_url", "oauth2_client_id_key",
                             "oauth2_client_secret_key", "oauth2_scopes", "oauth2_redirect_path"]
            for field in oauth2_fields:
                new_val = integration_data.get(field)
                if new_val and getattr(existing, field) != new_val:
                    setattr(existing, field, new_val)
                    updated = True
            if updated:
                logger.info(f"Updated OAuth2 config for integration: {integration_data['name']}")

    db.commit()


def seed_tools(db: Session):
    from app.models.tool_action import ToolAction
    from app.models.tool_permission import ToolPermission
    from app.models.permission import Permission

    tools = [
        {
            "name": "email_reader",
            "display_name": "Email Reader",
            "description": "Read and analyze emails",
            "category": "email",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": "gmail",
            "actions": [
                {"name": "read_email", "display_name": "Read Email", "description": "Read email content", "risk_level": "low", "requires_approval": False},
                {"name": "search_emails", "display_name": "Search Emails", "description": "Search email content", "risk_level": "low", "requires_approval": False},
                {"name": "list_inboxes", "display_name": "List Inboxes", "description": "List email inboxes", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["read_emails"]
        },
        {
            "name": "email_writer",
            "display_name": "Email Writer",
            "description": "Compose and send emails",
            "category": "email",
            "risk_level": "medium",
            "requires_approval": False,
            "integration_name": "gmail",
            "actions": [
                {"name": "send_email", "display_name": "Send Email", "description": "Send an email", "risk_level": "medium", "requires_approval": False},
                {"name": "create_draft", "display_name": "Create Draft", "description": "Create email draft", "risk_level": "low", "requires_approval": False},
                {"name": "manage_labels", "display_name": "Manage Labels", "description": "Manage email labels", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["write_emails"]
        },
        {
            "name": "knowledge_base",
            "display_name": "Knowledge Base",
            "description": "Access company knowledge base",
            "category": "knowledge",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "search_knowledge", "display_name": "Search Knowledge", "description": "Search knowledge base", "risk_level": "low", "requires_approval": False},
                {"name": "read_article", "display_name": "Read Article", "description": "Read knowledge article", "risk_level": "low", "requires_approval": False},
                {"name": "create_article", "display_name": "Create Article", "description": "Create knowledge article", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["read_knowledge"]
        },
        {
            "name": "ticket_system",
            "display_name": "Ticket System",
            "description": "Create and manage support tickets",
            "category": "support",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "create_ticket", "display_name": "Create Ticket", "description": "Create support ticket", "risk_level": "low", "requires_approval": False},
                {"name": "update_ticket", "display_name": "Update Ticket", "description": "Update ticket status", "risk_level": "low", "requires_approval": False},
                {"name": "list_tickets", "display_name": "List Tickets", "description": "List support tickets", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["create_tickets", "update_tickets"]
        },
        {
            "name": "content_editor",
            "display_name": "Content Editor",
            "description": "Create and edit content",
            "category": "content",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "create_content", "display_name": "Create Content", "description": "Create new content", "risk_level": "low", "requires_approval": False},
                {"name": "edit_content", "display_name": "Edit Content", "description": "Edit existing content", "risk_level": "low", "requires_approval": False},
                {"name": "publish_content", "display_name": "Publish Content", "description": "Publish content", "risk_level": "medium", "requires_approval": False}
            ],
            "permission_names": ["write_content"]
        },
        {
            "name": "seo_analyzer",
            "display_name": "SEO Analyzer",
            "description": "Analyze content for SEO optimization",
            "category": "content",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "analyze_seo", "display_name": "Analyze SEO", "description": "Analyze SEO metrics", "risk_level": "low", "requires_approval": False},
                {"name": "get_recommendations", "display_name": "Get Recommendations", "description": "Get SEO recommendations", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["read_content"]
        },
        {
            "name": "social_media_manager",
            "display_name": "Social Media Manager",
            "description": "Manage social media accounts",
            "category": "social",
            "risk_level": "medium",
            "requires_approval": True,
            "integration_name": "instagram",
            "actions": [
                {"name": "post_content", "display_name": "Post Content", "description": "Post to social media", "risk_level": "medium", "requires_approval": True},
                {"name": "manage_comments", "display_name": "Manage Comments", "description": "Manage comments", "risk_level": "low", "requires_approval": False},
                {"name": "view_analytics", "display_name": "View Analytics", "description": "View social analytics", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["manage_social_media"]
        },
        {
            "name": "analytics_tool",
            "display_name": "Analytics Tool",
            "description": "Analyze business metrics",
            "category": "analytics",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "get_metrics", "display_name": "Get Metrics", "description": "Get business metrics", "risk_level": "low", "requires_approval": False},
                {"name": "generate_report", "display_name": "Generate Report", "description": "Generate analytics report", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["read_analytics"]
        },
        {
            "name": "crm_tool",
            "display_name": "CRM Tool",
            "description": "Manage customer relationships",
            "category": "crm",
            "risk_level": "medium",
            "requires_approval": False,
            "integration_name": "crm",
            "actions": [
                {"name": "search_contacts", "display_name": "Search Contacts", "description": "Search customer contacts", "risk_level": "low", "requires_approval": False},
                {"name": "create_contact", "display_name": "Create Contact", "description": "Create new contact", "risk_level": "low", "requires_approval": False},
                {"name": "update_contact", "display_name": "Update Contact", "description": "Update contact info", "risk_level": "low", "requires_approval": False},
                {"name": "manage_deals", "display_name": "Manage Deals", "description": "Manage sales deals", "risk_level": "medium", "requires_approval": False}
            ],
            "permission_names": ["read_contacts", "write_contacts"]
        },
        {
            "name": "proposal_generator",
            "display_name": "Proposal Generator",
            "description": "Create sales proposals",
            "category": "sales",
            "risk_level": "medium",
            "requires_approval": True,
            "integration_name": None,
            "actions": [
                {"name": "create_proposal", "display_name": "Create Proposal", "description": "Create new proposal", "risk_level": "medium", "requires_approval": True},
                {"name": "send_proposal", "display_name": "Send Proposal", "description": "Send proposal to client", "risk_level": "high", "requires_approval": True}
            ],
            "permission_names": ["create_proposals"]
        },
        {
            "name": "web_search",
            "display_name": "Web Search",
            "description": "Search the web for information",
            "category": "research",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "search_web", "display_name": "Search Web", "description": "Search the web", "risk_level": "low", "requires_approval": False},
                {"name": "fetch_url", "display_name": "Fetch URL", "description": "Fetch URL content", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["web_search"]
        },
        {
            "name": "data_analyzer",
            "display_name": "Data Analyzer",
            "description": "Analyze data and generate insights",
            "category": "analytics",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "analyze_data", "display_name": "Analyze Data", "description": "Analyze data set", "risk_level": "low", "requires_approval": False},
                {"name": "generate_insights", "display_name": "Generate Insights", "description": "Generate data insights", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["read_analytics"]
        },
        {
            "name": "report_generator",
            "display_name": "Report Generator",
            "description": "Generate reports and documents",
            "category": "content",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "generate_report", "display_name": "Generate Report", "description": "Generate report", "risk_level": "low", "requires_approval": False},
                {"name": "export_document", "display_name": "Export Document", "description": "Export as document", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["write_content"]
        },
        {
            "name": "calendar_manager",
            "display_name": "Calendar Manager",
            "description": "Manage calendar and schedule",
            "category": "calendar",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": "google_calendar",
            "actions": [
                {"name": "read_events", "display_name": "Read Events", "description": "Read calendar events", "risk_level": "low", "requires_approval": False},
                {"name": "create_event", "display_name": "Create Event", "description": "Create calendar event", "risk_level": "low", "requires_approval": False},
                {"name": "manage_events", "display_name": "Manage Events", "description": "Manage calendar events", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["manage_calendar"]
        },
        {
            "name": "task_manager",
            "display_name": "Task Manager",
            "description": "Manage tasks and to-do lists",
            "category": "productivity",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "create_task", "display_name": "Create Task", "description": "Create new task", "risk_level": "low", "requires_approval": False},
                {"name": "update_task", "display_name": "Update Task", "description": "Update task status", "risk_level": "low", "requires_approval": False},
                {"name": "list_tasks", "display_name": "List Tasks", "description": "List tasks", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["manage_tasks"]
        },
        {
            "name": "chat_tool",
            "display_name": "Chat Tool",
            "description": "Real-time chat communication",
            "category": "communication",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": "slack",
            "actions": [
                {"name": "send_message", "display_name": "Send Message", "description": "Send chat message", "risk_level": "low", "requires_approval": False},
                {"name": "read_messages", "display_name": "Read Messages", "description": "Read chat messages", "risk_level": "low", "requires_approval": False},
                {"name": "manage_channels", "display_name": "Manage Channels", "description": "Manage chat channels", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["send_messages"]
        },
        {
            "name": "search_customers",
            "display_name": "Search Customers",
            "description": "Search customer database",
            "category": "crm",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": "crm",
            "actions": [
                {"name": "search_customers", "display_name": "Search Customers", "description": "Search customer database", "risk_level": "low", "requires_approval": False},
                {"name": "get_customer_details", "display_name": "Get Customer Details", "description": "Get customer details", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["read_contacts"]
        },
        {
            "name": "send_proposals",
            "display_name": "Send Proposals",
            "description": "Send proposals to clients",
            "category": "sales",
            "risk_level": "high",
            "requires_approval": True,
            "integration_name": None,
            "actions": [
                {"name": "send_proposal", "display_name": "Send Proposal", "description": "Send proposal to client", "risk_level": "high", "requires_approval": True}
            ],
            "permission_names": ["send_proposals"]
        },
        {
            "name": "create_invoices",
            "display_name": "Create Invoices",
            "description": "Create and send invoices",
            "category": "finance",
            "risk_level": "high",
            "requires_approval": True,
            "integration_name": None,
            "actions": [
                {"name": "create_invoice", "display_name": "Create Invoice", "description": "Create invoice", "risk_level": "high", "requires_approval": True},
                {"name": "send_invoice", "display_name": "Send Invoice", "description": "Send invoice to client", "risk_level": "high", "requires_approval": True}
            ],
            "permission_names": ["create_invoices"]
        },
        {
            "name": "database_query",
            "display_name": "Database Query",
            "description": "Query business database",
            "category": "data",
            "risk_level": "medium",
            "requires_approval": False,
            "integration_name": None,
            "actions": [
                {"name": "query_database", "display_name": "Query Database", "description": "Query database", "risk_level": "medium", "requires_approval": False},
                {"name": "export_data", "display_name": "Export Data", "description": "Export data", "risk_level": "medium", "requires_approval": False}
            ],
            "permission_names": ["database_query"]
        },
        {
            "name": "telegram_messaging",
            "display_name": "Telegram Messaging",
            "description": "Send and receive Telegram messages",
            "category": "communication",
            "risk_level": "medium",
            "requires_approval": False,
            "integration_name": "telegram",
            "actions": [
                {"name": "send_message", "display_name": "Send Message", "description": "Send Telegram message", "risk_level": "medium", "requires_approval": False},
                {"name": "read_messages", "display_name": "Read Messages", "description": "Read Telegram messages", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["send_messages"]
        },
        {
            "name": "telegram_account_messaging",
            "display_name": "Telegram Account Messaging",
            "description": "Send messages and read chat history as the connected Telegram user account (MTProto). Credentials stay server-side — agents only ever see message data.",
            "category": "communication",
            "risk_level": "medium",
            "requires_approval": False,
            "integration_name": "telegram_account",
            "actions": [
                {"name": "send_message", "display_name": "Send Message", "description": "Send a Telegram message as the connected user account", "risk_level": "medium", "requires_approval": False},
                {"name": "read_history", "display_name": "Read History", "description": "Read recent messages from a Telegram chat", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["telegram_account_send", "telegram_account_read"]
        },
        {
            "name": "discord_messaging",
            "display_name": "Discord Messaging",
            "description": "Send and receive Discord messages",
            "category": "communication",
            "risk_level": "medium",
            "requires_approval": False,
            "integration_name": "discord",
            "actions": [
                {"name": "send_message", "display_name": "Send Message", "description": "Send Discord message", "risk_level": "medium", "requires_approval": False},
                {"name": "read_messages", "display_name": "Read Messages", "description": "Read Discord messages", "risk_level": "low", "requires_approval": False},
                {"name": "manage_servers", "display_name": "Manage Servers", "description": "Manage Discord servers", "risk_level": "medium", "requires_approval": False}
            ],
            "permission_names": ["send_messages"]
        },
        {
            "name": "notion_pages",
            "display_name": "Notion Pages",
            "description": "Read and write Notion pages",
            "category": "productivity",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": "notion",
            "actions": [
                {"name": "read_pages", "display_name": "Read Pages", "description": "Read Notion pages", "risk_level": "low", "requires_approval": False},
                {"name": "write_pages", "display_name": "Write Pages", "description": "Write Notion pages", "risk_level": "low", "requires_approval": False},
                {"name": "search_content", "display_name": "Search Content", "description": "Search Notion content", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["read_knowledge", "write_content"]
        },
        {
            "name": "drive_files",
            "display_name": "Google Drive Files",
            "description": "Manage Google Drive files",
            "category": "productivity",
            "risk_level": "low",
            "requires_approval": False,
            "integration_name": "google_drive",
            "actions": [
                {"name": "read_files", "display_name": "Read Files", "description": "Read Drive files", "risk_level": "low", "requires_approval": False},
                {"name": "write_files", "display_name": "Write Files", "description": "Write Drive files", "risk_level": "low", "requires_approval": False},
                {"name": "share_files", "display_name": "Share Files", "description": "Share Drive files", "risk_level": "low", "requires_approval": False}
            ],
            "permission_names": ["read_files", "write_files"]
        }
    ]

    for tool_data in tools:
        integration_name = tool_data.pop("integration_name", None)
        actions_data = tool_data.pop("actions", [])
        permission_names = tool_data.pop("permission_names", [])
        
        integration_id = None
        if integration_name:
            integration = db.query(Integration).filter(Integration.name == integration_name).first()
            if integration:
                integration_id = integration.id

        existing = db.query(AgentTool).filter(AgentTool.name == tool_data["name"]).first()
        if not existing:
            tool = AgentTool(**tool_data, integration_id=integration_id)
            db.add(tool)
            db.flush()
            logger.info(f"Created tool: {tool_data['name']}" + (f" (integration: {integration_name})" if integration_name else ""))
            
            for action_data in actions_data:
                action = ToolAction(tool_id=tool.id, **action_data)
                db.add(action)
            
            for perm_name in permission_names:
                permission = db.query(Permission).filter(Permission.name == perm_name).first()
                if permission:
                    tool_perm = ToolPermission(tool_id=tool.id, permission_id=permission.id)
                    db.add(tool_perm)
        else:
            if integration_id and existing.integration_id != integration_id:
                existing.integration_id = integration_id
                logger.info(f"Updated tool: {tool_data['name']} -> integration: {integration_name}")
            if "category" in tool_data and existing.category != tool_data["category"]:
                existing.category = tool_data["category"]

    db.commit()


def seed_permissions(db: Session):
    permissions = [
        {"name": "read_emails", "description": "Read emails", "category": "email", "risk_level": "low"},
        {"name": "write_emails", "description": "Write and send emails", "category": "email", "risk_level": "medium"},
        {"name": "create_tickets", "description": "Create support tickets", "category": "support", "risk_level": "low"},
        {"name": "read_tickets", "description": "Read support tickets", "category": "support", "risk_level": "low"},
        {"name": "write_tickets", "description": "Update support tickets", "category": "support", "risk_level": "low"},
        {"name": "search_customers", "description": "Search customer database", "category": "crm", "risk_level": "low"},
        {"name": "read_leads", "description": "Read sales leads", "category": "sales", "risk_level": "low"},
        {"name": "write_leads", "description": "Update sales leads", "category": "sales", "risk_level": "low"},
        {"name": "send_proposals", "description": "Send proposals to clients", "category": "sales", "risk_level": "high", "default_approval_required": True},
        {"name": "create_invoices", "description": "Create invoices", "category": "finance", "risk_level": "high", "default_approval_required": True},
        {"name": "read_knowledge", "description": "Read company knowledge base", "category": "knowledge", "risk_level": "low"},
        {"name": "write_knowledge", "description": "Write to knowledge base", "category": "knowledge", "risk_level": "medium"},
        {"name": "write_content", "description": "Create content", "category": "content", "risk_level": "low"},
        {"name": "publish_content", "description": "Publish content", "category": "content", "risk_level": "high", "default_approval_required": True},
        {"name": "read_social", "description": "Read social media", "category": "social", "risk_level": "low"},
        {"name": "write_social", "description": "Write social media posts", "category": "social", "risk_level": "medium"},
        {"name": "schedule_posts", "description": "Schedule social media posts", "category": "social", "risk_level": "medium"},
        {"name": "search_web", "description": "Search the web", "category": "research", "risk_level": "low"},
        {"name": "analyze_data", "description": "Analyze data", "category": "analytics", "risk_level": "low"},
        {"name": "read_analytics", "description": "Read analytics data", "category": "analytics", "risk_level": "low"},
        {"name": "write_reports", "description": "Create reports", "category": "analytics", "risk_level": "low"},
        {"name": "access_database", "description": "Access business database", "category": "data", "risk_level": "medium"},
        {"name": "access_knowledge_base", "description": "Access knowledge base", "category": "knowledge", "risk_level": "low"},
        {"name": "read_calendar", "description": "Read calendar", "category": "calendar", "risk_level": "low"},
        {"name": "write_calendar", "description": "Write to calendar", "category": "calendar", "risk_level": "low"},
        {"name": "manage_emails", "description": "Manage email accounts", "category": "email", "risk_level": "medium"},
        {"name": "schedule_meetings", "description": "Schedule meetings", "category": "calendar", "risk_level": "low"},
        {"name": "issue_refunds", "description": "Issue refunds", "category": "finance", "risk_level": "high", "default_approval_required": True},
        {"name": "delete_customer", "description": "Delete customer data", "category": "crm", "risk_level": "critical", "default_approval_required": True},
        {"name": "financial_transfer", "description": "Make financial transfers", "category": "finance", "risk_level": "critical", "default_approval_required": True},
        {"name": "send_messages", "description": "Send messages via connected messaging integrations", "category": "communication", "risk_level": "medium"},
        {"name": "telegram_account_send", "description": "Send Telegram messages via the connected Telegram user account", "category": "communication", "risk_level": "medium"},
        {"name": "telegram_account_read", "description": "Read Telegram chat history via the connected Telegram user account", "category": "communication", "risk_level": "low"}
    ]

    for perm_data in permissions:
        existing = db.query(Permission).filter(Permission.name == perm_data["name"]).first()
        if not existing:
            permission = Permission(**perm_data)
            db.add(permission)
            logger.info(f"Created permission: {perm_data['name']}")

    db.commit()


def seed_telegram_account_tool_permissions(db: Session):
    """Link the Telegram messaging tools to their permissions (idempotent).

    Runs after seed_permissions: ToolPermission rows need the Permission rows
    to exist, and seed_tools runs before seed_permissions in seed_all (its
    existing-tool branch never back-fills permission links). Deliberately
    scoped to the two Telegram tools only so no other tool's permission
    surface changes.
    """
    # telegram_account_messaging → account permissions (MTProto)
    tool = db.query(AgentTool).filter(AgentTool.name == "telegram_account_messaging").first()
    if tool:
        linked = {
            tp.permission_id
            for tp in db.query(ToolPermission).filter(ToolPermission.tool_id == tool.id).all()
        }
        for perm_name in ("telegram_account_send", "telegram_account_read"):
            permission = db.query(Permission).filter(Permission.name == perm_name).first()
            if permission and permission.id not in linked:
                db.add(ToolPermission(tool_id=tool.id, permission_id=permission.id))
                logger.info(f"Linked permission {perm_name} to tool telegram_account_messaging")

    # telegram_messaging → bot send permission (Bot API customer chat)
    bot_tool = db.query(AgentTool).filter(AgentTool.name == "telegram_messaging").first()
    if bot_tool:
        linked_bot = {
            tp.permission_id
            for tp in db.query(ToolPermission).filter(ToolPermission.tool_id == bot_tool.id).all()
        }
        permission = db.query(Permission).filter(Permission.name == "send_messages").first()
        if permission and permission.id not in linked_bot:
            db.add(ToolPermission(tool_id=bot_tool.id, permission_id=permission.id))
            logger.info("Linked permission send_messages to tool telegram_messaging")

    db.commit()


def seed_all(db: Session):
    logger.info("Seeding templates...")
    seed_templates(db)
    logger.info("Seeding integrations...")
    seed_integrations(db)
    logger.info("Seeding tools...")
    seed_tools(db)
    logger.info("Seeding permissions...")
    seed_permissions(db)
    seed_telegram_account_tool_permissions(db)
    logger.info("Seed completed!")
