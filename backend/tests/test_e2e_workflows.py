"""End-to-end workflow tests: Tool→Permission→Risk→Approval→Execution,
Agent→Integration→ExternalAction, Document→Chunk→Embedding→Retrieval→Context.

These tests exercise the full pipeline across multiple services, mocking only
external network calls (LLM, email providers, WebSocket broadcasts, event bus).
All database state is rolled back after each test via the Neon ``db`` fixture.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.user import User
from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.tool import AgentTool
from app.models.permission import Permission
from app.models.agent_permission import AgentPermission
from app.models.knowledge import KnowledgeSource, KnowledgeStatus
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.agent_knowledge import AgentKnowledgeAccess

from app.schemas.permission import AgentPermissionCreate, PermissionCreate
from app.schemas.risk_rule import RiskRuleCreate
from app.schemas.integration import IntegrationCreate, IntegrationAccountCreate

from app.services.tool_execution_service import ToolExecutionService
from app.services.permission_service import PermissionService
from app.services.risk_rule_service import RiskRuleService, RiskEvaluationService
from app.services.approval_service import ApprovalService
from app.services.integration_service import IntegrationService
from app.services.knowledge_service import KnowledgeService
from app.services.rag_service import RAGService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _activate_agent(agent: AIAgent, db, tool_names: str = ""):
    """Set agent to active lifecycle and optionally assign tools."""
    agent.lifecycle_status = LifecycleStatus.ACTIVE
    agent.status = AgentStatus.ACTIVE
    agent.tools = tool_names
    db.flush()


def _make_ceo(db) -> User:
    """Create a CEO user in the Neon DB for approval tests."""
    ceo = User(
        id=uuid4(),
        email=f"ceo_{uuid4().hex[:8]}@example.com",
        name="E2E CEO",
        role="user",
        is_active=True,
    )
    db.add(ceo)
    db.flush()
    return ceo


# ---------------------------------------------------------------------------
# Workflow 1: Tool -> Permission -> Risk -> Approval -> Execution
# ---------------------------------------------------------------------------

class TestWorkflowToolPermissionRiskApprovalExecution:
    """Full pipeline: create tool, permission, risk rule, assign to agent,
    execute, get approval, approve, execute again."""

    def test_full_pipeline(self, db, neon_user, neon_agent, neon_tool,
                           neon_permission):
        # -- Activate agent with the tool assigned -------------------------
        _activate_agent(neon_agent, db, tool_names=neon_tool.name)

        # -- 1. Create a risk rule that marks 'send_email' as HIGH risk ----
        risk_service = RiskRuleService(db)
        high_risk_rule = risk_service.create_risk_rule(
            RiskRuleCreate(
                name="High Risk Email Rule",
                description="All email sends require CEO approval",
                action_name="send_email",
                risk_level="high",
                requires_approval=True,
                priority=10,
                is_active=True,
            )
        )
        assert high_risk_rule.risk_level == "high"
        assert high_risk_rule.requires_approval is True

        # -- 2. Create a permission for the tool ---------------------------
        perm_service = PermissionService(db)
        email_permission = perm_service.create_permission(
            PermissionCreate(
                name="email.send",
                description="Permission to send emails",
                category="email",
                risk_level="high",
                default_status="allowed",
                is_active=True,
            )
        )
        assert email_permission.name == "email.send"

        # -- 3. Assign permission to the agent -----------------------------
        perm_service.set_agent_permission(
            agent_id=neon_agent.id,
            data=AgentPermissionCreate(
                permission_id=email_permission.id,
                access_level="allowed",
                notes="E2E test permission",
            ),
        )

        # -- 4. Evaluate risk → should return HIGH + requires approval -----
        eval_service = RiskEvaluationService(db)
        risk_level, requires_approval, rule_id, rule_name, reason = (
            eval_service.evaluate_risk(neon_agent.id, neon_tool.name, "send_email")
        )
        assert risk_level == "high"
        assert requires_approval is True
        assert rule_id == high_risk_rule.id

        # -- 5. Execute tool → should create approval request ---------------
        with patch("app.services.integration_providers.registry.get_provider", return_value=None):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=neon_tool.name,
                action="send_email",
                parameters={"to": "recipient@example.com", "subject": "Hello"},
                reason="E2E workflow test",
            )

        assert result["success"] is False
        assert result["requires_approval"] is True
        assert "approval_id" in result
        assert result["risk_level"] == "high"

        approval_id = result["approval_id"]

        # -- 6. CEO approves the approval -----------------------------------
        approval_service = ApprovalService(db)
        ceo = _make_ceo(db)

        approval = approval_service.approve(
            approval_id=approval_id,
            decided_by=ceo.id,
            notes="Approved for E2E test",
        )
        assert approval is not None
        assert approval.status == "approved"
        assert approval.decision_notes == "Approved for E2E test"
        assert str(approval.decided_by) == str(ceo.id)

        # -- 7. Verify execution result is attached to approval -------------
        db.refresh(approval)
        params = approval.parameters or {}
        assert "_execution_result" in params
        exec_result = params["_execution_result"]
        assert exec_result["success"] is True
        assert "executed" in exec_result["message"].lower() or "action" in exec_result["message"].lower()

    def test_permission_denied_blocks_execution(self, db, neon_user,
                                                neon_agent, neon_tool,
                                                neon_permission):
        """Agent without permission gets blocked before risk evaluation."""
        _activate_agent(neon_agent, db, tool_names=neon_tool.name)

        with patch("app.services.integration_providers.registry.get_provider", return_value=None):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=neon_tool.name,
                action="send_email",
                parameters={"to": "test@example.com"},
            )

        assert result["success"] is False
        assert "permission" in result["error"].lower() or "missing" in result["error"].lower()

    def test_low_risk_auto_executes(self, db, neon_user, neon_agent,
                                    neon_tool, neon_permission):
        """Low-risk action with no approval-required rule auto-executes."""
        _activate_agent(neon_agent, db, tool_names=neon_tool.name)

        perm_service = PermissionService(db)
        perm_service.set_agent_permission(
            agent_id=neon_agent.id,
            data=AgentPermissionCreate(
                permission_id=neon_permission.id,
                access_level="allowed",
            ),
        )

        with patch("app.services.integration_providers.registry.get_provider", return_value=None):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=neon_tool.name,
                action="read_data",
                parameters={},
            )

        assert result["success"] is True
        assert result.get("auto_approved") is True

    def test_inactive_agent_blocked(self, db, neon_tool, neon_permission):
        """Agent with draft lifecycle cannot execute tools."""
        agent = AIAgent(
            id=uuid4(),
            name="Draft Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.DRAFT,
            tools=neon_tool.name,
        )
        db.add(agent)
        db.flush()

        with patch("app.services.integration_providers.registry.get_provider", return_value=None):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=agent.id,
                tool_name=neon_tool.name,
                action="read_data",
            )

        assert result["success"] is False
        assert "not active" in result["error"].lower()

    def test_tool_not_assigned_blocked(self, db, neon_user, neon_agent,
                                      neon_permission):
        """Agent without tool in tools string gets blocked."""
        _activate_agent(neon_agent, db, tool_names="")

        with patch("app.services.integration_providers.registry.get_provider", return_value=None):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name="some_tool",
                action="read_data",
            )

        assert result["success"] is False
        assert "not assigned" in result["error"].lower()


# ---------------------------------------------------------------------------
# Workflow 2: Agent -> Integration -> External Action
# ---------------------------------------------------------------------------

class TestWorkflowAgentIntegrationExternalAction:
    """Create integration, assign to agent, execute via tool with provider."""

    def test_full_integration_pipeline(self, db, neon_user, neon_agent):
        # -- 1. Create a gmail integration ----------------------------------
        integration_service = IntegrationService(db)
        gmail = integration_service.create_integration(
            IntegrationCreate(
                name="gmail",
                display_name="Gmail",
                description="Google Mail integration",
                auth_type="oauth2",
                is_active=True,
            )
        )
        assert gmail.name == "gmail"

        # -- 2. Create integration account with credentials -----------------
        account = integration_service.create_account(
            user_id=neon_user.id,
            data=IntegrationAccountCreate(
                integration_id=gmail.id,
                display_name="Personal Gmail",
                credentials={"api_key": "test-api-key-12345"},
                status="connected",
            )
        )
        assert account.status == "connected"
        assert account.integration_id == gmail.id

        # -- 3. Assign integration to agent ---------------------------------
        agent_int = integration_service.assign_integration_to_agent(
            agent_id=neon_agent.id,
            integration_id=gmail.id,
            capabilities=["send_email", "read_email"],
        )
        assert agent_int is not None
        assert agent_int.is_active is True

        # -- 4. Create tool linked to the integration -----------------------
        tool = AgentTool(
            id=uuid4(),
            name="gmail_tool",
            display_name="Gmail Tool",
            description="Send and read emails via Gmail",
            category="email",
            integration_id=gmail.id,
            risk_level="low",
            requires_approval=False,
            is_active=True,
        )
        db.add(tool)
        db.flush()

        # Activate agent with tool
        _activate_agent(neon_agent, db, tool_names=tool.name)

        # Grant permission
        perm_service = PermissionService(db)
        perm = Permission(
            id=uuid4(),
            name="gmail.send",
            description="Gmail send permission",
            category="email",
            risk_level="low",
            default_status="allowed",
            is_active=True,
        )
        db.add(perm)
        db.flush()

        perm_service.set_agent_permission(
            agent_id=neon_agent.id,
            data=AgentPermissionCreate(
                permission_id=perm.id,
                access_level="allowed",
            ),
        )

        # -- 5. Mock provider and execute -----------------------------------
        mock_provider = AsyncMock()
        mock_provider.execute_action = AsyncMock(return_value=MagicMock(
            success=True,
            data={"message_id": "msg_123", "status": "sent"},
            error=None,
        ))

        with patch(
            "app.services.integration_providers.registry.get_provider",
            return_value=mock_provider,
        ):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=tool.name,
                action="send_email",
                parameters={
                    "to": "recipient@example.com",
                    "subject": "Test Email",
                    "body": "Hello from E2E test!",
                },
            )

        assert result["success"] is True
        assert result["data"]["message_id"] == "msg_123"
        mock_provider.execute_action.assert_called_once()

    def test_integration_account_credential_retrieval(self, db, neon_user,
                                                     neon_agent):
        """Verify credentials are decrypted when passed to provider."""
        integration_service = IntegrationService(db)
        gmail = integration_service.create_integration(
            IntegrationCreate(
                name="gmail",
                display_name="Gmail",
                auth_type="oauth2",
                is_active=True,
            )
        )

        account = integration_service.create_account(
            user_id=neon_user.id,
            data=IntegrationAccountCreate(
                integration_id=gmail.id,
                credentials={"api_key": "secret-key-abc"},
                status="connected",
            )
        )

        tool = AgentTool(
            id=uuid4(),
            name="gmail_tool",
            display_name="Gmail Tool",
            category="email",
            integration_id=gmail.id,
            risk_level="low",
            is_active=True,
        )
        db.add(tool)
        db.flush()

        _activate_agent(neon_agent, db, tool_names=tool.name)

        perm_service = PermissionService(db)
        perm = Permission(
            id=uuid4(),
            name="gmail.access",
            description="Gmail access",
            category="email",
            risk_level="low",
            default_status="allowed",
            is_active=True,
        )
        db.add(perm)
        db.flush()

        perm_service.set_agent_permission(
            agent_id=neon_agent.id,
            data=AgentPermissionCreate(
                permission_id=perm.id,
                access_level="allowed",
            ),
        )

        captured_kwargs = {}

        async def _capture_action(action, parameters, access_token=None,
                                  credentials=None):
            captured_kwargs["action"] = action
            captured_kwargs["parameters"] = parameters
            captured_kwargs["credentials"] = credentials
            captured_kwargs["access_token"] = access_token
            return MagicMock(success=True, data={}, error=None)

        mock_provider = AsyncMock()
        mock_provider.execute_action = AsyncMock(side_effect=_capture_action)

        with patch(
            "app.services.integration_providers.registry.get_provider",
            return_value=mock_provider,
        ):
            exec_service = ToolExecutionService(db)
            exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=tool.name,
                action="read_inbox",
                parameters={"max_results": 10},
            )

        assert captured_kwargs["action"] == "read_inbox"
        assert captured_kwargs["credentials"]["api_key"] == "secret-key-abc"

    def test_integration_approval_required_flow(self, db, neon_user,
                                                neon_agent):
        """High-risk integration action goes through approval."""
        integration_service = IntegrationService(db)
        gmail = integration_service.create_integration(
            IntegrationCreate(
                name="gmail",
                display_name="Gmail",
                auth_type="oauth2",
                is_active=True,
            )
        )

        account = integration_service.create_account(
            user_id=neon_user.id,
            data=IntegrationAccountCreate(
                integration_id=gmail.id,
                credentials={"api_key": "test"},
                status="connected",
            )
        )

        tool = AgentTool(
            id=uuid4(),
            name="gmail_tool",
            display_name="Gmail Tool",
            category="email",
            integration_id=gmail.id,
            risk_level="low",
            requires_approval=False,
            is_active=True,
        )
        db.add(tool)
        db.flush()

        _activate_agent(neon_agent, db, tool_names=tool.name)

        perm = Permission(
            id=uuid4(),
            name="gmail.send",
            description="Gmail send",
            category="email",
            risk_level="low",
            default_status="allowed",
            is_active=True,
        )
        db.add(perm)
        db.flush()

        PermissionService(db).set_agent_permission(
            agent_id=neon_agent.id,
            data=AgentPermissionCreate(
                permission_id=perm.id,
                access_level="allowed",
            ),
        )

        # Risk rule requires approval for send_proposal action
        RiskRuleService(db).create_risk_rule(
            RiskRuleCreate(
                name="Proposal Approval",
                action_name="send_proposal",
                risk_level="high",
                requires_approval=True,
                priority=10,
            )
        )

        ceo = _make_ceo(db)

        with patch(
            "app.services.integration_providers.registry.get_provider",
            return_value=None,
        ):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=tool.name,
                action="send_proposal",
                parameters={"client": "Acme Corp", "amount": 50000},
            )

        assert result["requires_approval"] is True
        approval_id = result["approval_id"]

        approval_service = ApprovalService(db)
        approval = approval_service.approve(
            approval_id=approval_id,
            decided_by=ceo.id,
            notes="Approved deal",
        )
        assert approval.status == "approved"


# ---------------------------------------------------------------------------
# Workflow 3: Document -> Chunk -> Embedding -> Retrieval -> Agent Context
# ---------------------------------------------------------------------------

class TestWorkflowDocumentChunkEmbeddingRetrievalContext:
    """Full RAG pipeline: ingest, search, assemble context for agent."""

    @pytest.mark.asyncio
    async def test_full_rag_pipeline(self, db, neon_user, neon_agent,
                                     neon_knowledge, mock_embedding_provider):
        # -- 1. Grant agent access to knowledge -----------------------------
        knowledge_service = KnowledgeService(db)
        knowledge_service.grant_access(
            agent_id=neon_agent.id,
            knowledge_id=neon_knowledge.id,
        )

        # Verify access was granted
        access = db.query(AgentKnowledgeAccess).filter(
            AgentKnowledgeAccess.agent_id == neon_agent.id,
            AgentKnowledgeAccess.knowledge_id == neon_knowledge.id,
        ).first()
        assert access is not None
        assert access.access_level == "read"

        # -- 2. Ingest knowledge (chunk + embed) ----------------------------
        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            rag_service = RAGService(db)
            ingest_result = await rag_service.ingest_knowledge(neon_knowledge.id)

        assert ingest_result["chunk_count"] >= 1
        assert ingest_result["dimensions"] == mock_embedding_provider.default_dimensions

        # Verify chunks were created in the DB
        chunks = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.knowledge_id == neon_knowledge.id,
        ).all()
        assert len(chunks) >= 1
        assert all(c.embedding is not None for c in chunks)
        assert all(c.content for c in chunks)

        # Verify source status updated
        db.refresh(neon_knowledge)
        assert neon_knowledge.status == KnowledgeStatus.ACTIVE.value
        assert int(neon_knowledge.chunk_count) >= 1

        # -- 3. Search for relevant content ---------------------------------
        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            search_results = await rag_service.search(
                query="Python programming language",
                top_k=5,
            )

        assert len(search_results) >= 1
        # The mock embedding produces deterministic vectors, so search should
        # find chunks from our ingested knowledge
        found_knowledge = any(
            str(r["knowledge_id"]) == str(neon_knowledge.id)
            for r in search_results
        )
        assert found_knowledge, (
            f"Expected to find chunks from knowledge {neon_knowledge.id} "
            f"in search results: {[str(r['knowledge_id']) for r in search_results]}"
        )

        # Verify source metadata is attached
        for result in search_results:
            if str(result["knowledge_id"]) == str(neon_knowledge.id):
                assert "source_name" in result
                assert result["source_name"] == neon_knowledge.name
                break

        # -- 4. Search with permission filtering ----------------------------
        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            perm_search = await rag_service.search_with_permissions(
                query="Python programming",
                agent_id=neon_agent.id,
                top_k=5,
            )

        assert len(perm_search) >= 1
        perm_found = any(
            str(r["knowledge_id"]) == str(neon_knowledge.id)
            for r in perm_search
        )
        assert perm_found

        # -- 5. Assemble context for agent ----------------------------------
        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            context = await rag_service.assemble_context(
                query="Tell me about Python",
                agent_id=neon_agent.id,
            )

        assert "context" in context
        assert "sources" in context
        assert "chunks" in context
        assert len(context["chunks"]) >= 1
        assert len(context["sources"]) >= 1

        # Verify context contains the right content
        ctx_text = context["context"].lower()
        assert "python" in ctx_text

        # Verify citation metadata
        source = context["sources"][0]
        assert source["knowledge_id"] == str(neon_knowledge.id)
        assert source["source_name"] == neon_knowledge.name

    @pytest.mark.asyncio
    async def test_search_without_access_returns_empty(self, db, neon_user,
                                                       neon_agent,
                                                       neon_knowledge,
                                                       mock_embedding_provider):
        """Agent without access to knowledge gets no search results."""
        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            rag_service = RAGService(db)
            await rag_service.ingest_knowledge(neon_knowledge.id)

        # No access granted
        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            perm_search = await rag_service.search_with_permissions(
                query="Python",
                agent_id=neon_agent.id,
                top_k=5,
            )

        assert len(perm_search) == 0

    @pytest.mark.asyncio
    async def test_context_assembly_respects_max_length(self, db, neon_user,
                                                        neon_agent,
                                                        mock_embedding_provider):
        """Context assembly truncates to max_context_length."""
        long_content = "Python is great. " * 500  # ~8000 chars
        source = KnowledgeSource(
            id=uuid4(),
            name="Long Document",
            description="Very long content",
            category="general",
            content=long_content,
            source_type="text",
            status="active",
            chunk_count="0",
            created_by=neon_user.id,
        )
        db.add(source)
        db.flush()

        knowledge_service = KnowledgeService(db)
        knowledge_service.grant_access(
            agent_id=neon_agent.id,
            knowledge_id=source.id,
        )

        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            rag_service = RAGService(db)
            await rag_service.ingest_knowledge(source.id)

        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            context = await rag_service.assemble_context(
                query="Python programming",
                agent_id=neon_agent.id,
                max_context_length=1000,
            )

        assert len(context["context"]) <= 1200  # Allow some overhead for citation labels

    @pytest.mark.asyncio
    async def test_multiple_knowledge_sources_ranked(self, db, neon_user,
                                                     neon_agent,
                                                     mock_embedding_provider):
        """Multiple sources are returned and ranked by similarity."""
        source1 = KnowledgeSource(
            id=uuid4(),
            name="Python Guide",
            description="Python basics",
            category="programming",
            content="Python is a high-level programming language known for its readability and versatility.",
            source_type="text",
            status="active",
            chunk_count="0",
            created_by=neon_user.id,
        )
        source2 = KnowledgeSource(
            id=uuid4(),
            name="Java Guide",
            description="Java basics",
            category="programming",
            content="Java is a compiled, object-oriented programming language used in enterprise applications.",
            source_type="text",
            status="active",
            chunk_count="0",
            created_by=neon_user.id,
        )
        db.add(source1)
        db.add(source2)
        db.flush()

        knowledge_service = KnowledgeService(db)
        knowledge_service.grant_access(neon_agent.id, source1.id)
        knowledge_service.grant_access(neon_agent.id, source2.id)

        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            rag_service = RAGService(db)
            await rag_service.ingest_knowledge(source1.id)
            await rag_service.ingest_knowledge(source2.id)

        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            search_results = await rag_service.search(
                query="Python programming",
                top_k=5,
            )

        assert len(search_results) >= 2
        found_ids = {str(r["knowledge_id"]) for r in search_results}
        assert str(source1.id) in found_ids
        assert str(source2.id) in found_ids

    @pytest.mark.asyncio
    async def test_reprocess_knowledge(self, db, neon_user, neon_agent,
                                       neon_knowledge,
                                       mock_embedding_provider):
        """Reprocessing re-creates chunks and embeddings."""
        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            rag_service = RAGService(db)
            await rag_service.ingest_knowledge(neon_knowledge.id)

        initial_count = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.knowledge_id == neon_knowledge.id,
        ).count()
        assert initial_count >= 1

        # Delete and re-ingest
        with patch(
            "app.services.rag_service.get_embedding_provider",
            return_value=mock_embedding_provider,
        ):
            result = await rag_service.reprocess_knowledge(neon_knowledge.id)

        assert result["chunk_count"] >= 1
        final_count = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.knowledge_id == neon_knowledge.id,
        ).count()
        assert final_count >= 1


# ---------------------------------------------------------------------------
# Cross-Workflow: Risk + Approval + Integration combined
# ---------------------------------------------------------------------------

class TestCrossWorkflowRiskApprovalIntegration:
    """Verify risk rules trigger correctly for integration-backed tools."""

    def test_risk_rule_blocks_integration_action(self, db, neon_user,
                                                 neon_agent):
        integration_service = IntegrationService(db)
        slack = integration_service.create_integration(
            IntegrationCreate(
                name="slack",
                display_name="Slack",
                auth_type="bot_token",
                is_active=True,
            )
        )

        account = integration_service.create_account(
            user_id=neon_user.id,
            data=IntegrationAccountCreate(
                integration_id=slack.id,
                credentials={"bot_token": "xoxb-test-token"},
                status="connected",
            )
        )

        tool = AgentTool(
            id=uuid4(),
            name="slack_tool",
            display_name="Slack Tool",
            category="communication",
            integration_id=slack.id,
            risk_level="medium",
            requires_approval=False,
            is_active=True,
        )
        db.add(tool)
        db.flush()

        _activate_agent(neon_agent, db, tool_names=tool.name)

        perm = Permission(
            id=uuid4(),
            name="slack.send",
            description="Slack send",
            category="communication",
            risk_level="low",
            default_status="allowed",
            is_active=True,
        )
        db.add(perm)
        db.flush()

        PermissionService(db).set_agent_permission(
            agent_id=neon_agent.id,
            data=AgentPermissionCreate(
                permission_id=perm.id,
                access_level="allowed",
            ),
        )

        # Critical risk rule for publishing content
        RiskRuleService(db).create_risk_rule(
            RiskRuleCreate(
                name="Critical Publish",
                action_name="publish_content",
                risk_level="critical",
                requires_approval=True,
                priority=20,
            )
        )

        ceo = _make_ceo(db)

        with patch(
            "app.services.integration_providers.registry.get_provider",
            return_value=None,
        ):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=tool.name,
                action="publish_content",
                parameters={"channel": "#general", "message": "Hello world"},
            )

        assert result["requires_approval"] is True
        assert result["risk_level"] == "critical"

        approval_service = ApprovalService(db)
        approval = approval_service.approve(
            approval_id=result["approval_id"],
            decided_by=ceo.id,
            notes="Safe to publish",
        )
        assert approval.status == "approved"

    def test_conditional_risk_rule_with_parameters(self, db, neon_user,
                                                   neon_agent):
        """Risk rule with conditions only triggers when params match."""
        tool = AgentTool(
            id=uuid4(),
            name="payment_tool",
            display_name="Payment Tool",
            category="finance",
            risk_level="low",
            requires_approval=False,
            is_active=True,
        )
        db.add(tool)
        db.flush()

        _activate_agent(neon_agent, db, tool_names=tool.name)

        perm = Permission(
            id=uuid4(),
            name="payment.refund",
            description="Payment refund",
            category="finance",
            risk_level="low",
            default_status="allowed",
            is_active=True,
        )
        db.add(perm)
        db.flush()

        PermissionService(db).set_agent_permission(
            agent_id=neon_agent.id,
            data=AgentPermissionCreate(
                permission_id=perm.id,
                access_level="allowed",
            ),
        )

        RiskRuleService(db).create_risk_rule(
            RiskRuleCreate(
                name="Large Refund",
                action_name="issue_refund",
                risk_level="critical",
                requires_approval=True,
                conditions={"amount": {"min": 1000}},
                priority=10,
            )
        )

        ceo = _make_ceo(db)

        # Small refund → auto-executes
        with patch(
            "app.services.integration_providers.registry.get_provider",
            return_value=None,
        ):
            exec_service = ToolExecutionService(db)
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=tool.name,
                action="issue_refund",
                parameters={"amount": 50},
            )

        assert result["success"] is True
        assert result.get("auto_approved") is True

        # Large refund → requires approval
        with patch(
            "app.services.integration_providers.registry.get_provider",
            return_value=None,
        ):
            result = exec_service.execute_tool(
                agent_id=neon_agent.id,
                tool_name=tool.name,
                action="issue_refund",
                parameters={"amount": 5000},
            )

        assert result["requires_approval"] is True

        approval_service = ApprovalService(db)
        approval = approval_service.approve(
            approval_id=result["approval_id"],
            decided_by=ceo.id,
            notes="Approved large refund",
        )
        assert approval.status == "approved"
