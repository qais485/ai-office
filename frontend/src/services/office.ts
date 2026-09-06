import { api } from './api'
import type { OfficeRoom, AIAgent, Task, TaskStats, CreateRoomRequest, CreateAgentRequest, UpdateAgentRequest, DashboardSummary, EmailMessage, CreateEmailRequest, EmailStats, AgentActivity, EmailAccount, CreateEmailAccountRequest, AgentTemplate, HireAgentRequest, AgentTool, ToolWithActions, Permission, AgentPermission, Integration, IntegrationAccount, Approval, ApprovalStats, RiskRule, RiskSummary, Knowledge, KnowledgeStats, KnowledgeAgentAccess, CEOSummary, CEOAgentOverview, CEOActivity, CEOPerformance, CEOInboxItem, CEOInboxCounts, CompanyAnalytics, AgentRankingItem, DailyStatsItem } from '../types'

export const officeService = {
  async getRooms() {
    return api.get<OfficeRoom[]>('rooms/')
  },

  async getRoom(id: string) {
    return api.get<OfficeRoom>(`rooms/${id}`)
  },

  async createRoom(data: CreateRoomRequest) {
    return api.post<OfficeRoom>('rooms/', data)
  },

  async updateRoom(id: string, data: Partial<CreateRoomRequest>) {
    return api.put<OfficeRoom>(`rooms/${id}`, data)
  },

  async deleteRoom(id: string) {
    return api.delete(`rooms/${id}`)
  },

  async getAgents() {
    return api.get<AIAgent[]>('agents/')
  },

  async getAgent(id: string) {
    return api.get<AIAgent>(`agents/${id}`)
  },

  async createAgent(data: CreateAgentRequest) {
    return api.post<AIAgent>('agents/', data)
  },

  async updateAgent(id: string, data: UpdateAgentRequest) {
    return api.put<AIAgent>(`agents/${id}`, data)
  },

  async getTasks(filters?: { status?: string; priority?: string; task_type?: string; agent_id?: string }) {
    const params = new URLSearchParams()
    if (filters?.status) params.set('status', filters.status)
    if (filters?.priority) params.set('priority', filters.priority)
    if (filters?.task_type) params.set('task_type', filters.task_type)
    if (filters?.agent_id) params.set('agent_id', filters.agent_id)
    const qs = params.toString()
    return api.get<Task[]>(`tasks/${qs ? `?${qs}` : ''}`)
  },

  async getTaskStats(agentId?: string) {
    const params = agentId ? `?agent_id=${agentId}` : ''
    return api.get<TaskStats>(`tasks/stats/summary${params}`)
  },

  async startTask(taskId: string) {
    return api.post<Task>(`tasks/${taskId}/start`)
  },

  async completeTask(taskId: string, result?: string) {
    const params = result ? `?result=${encodeURIComponent(result)}` : ''
    return api.post<Task>(`tasks/${taskId}/complete${params}`)
  },

  async failTask(taskId: string, errorMessage: string) {
    return api.post<Task>(`tasks/${taskId}/fail?error_message=${encodeURIComponent(errorMessage)}`)
  },

  async cancelTask(taskId: string) {
    return api.post<Task>(`tasks/${taskId}/cancel`)
  },

  async handoffTask(taskId: string, toAgentId: string) {
    return api.post<Task>(`tasks/${taskId}/handoff?to_agent_id=${toAgentId}`)
  },

  async getTasksByAgent(agentId: string) {
    const result = await api.get<Task[]>(`tasks/?agent_id=${agentId}`)
    return result
  },

  async getDashboardSummary() {
    return api.get<DashboardSummary>('dashboard/summary')
  },

  async getEmails(agentId?: string) {
    const params = agentId ? `?agent_id=${agentId}` : ''
    return api.get<EmailMessage[]>(`emails/${params}`)
  },

  async getEmail(id: string) {
    return api.get<EmailMessage>(`emails/${id}`)
  },

  async createEmail(data: CreateEmailRequest) {
    return api.post<EmailMessage>('emails/', data)
  },

  async processEmail(id: string) {
    return api.post<EmailMessage>(`emails/${id}/process`)
  },

  async getEmailStats(agentId?: string) {
    const params = agentId ? `?agent_id=${agentId}` : ''
    return api.get<EmailStats>(`emails/stats${params}`)
  },

  async deleteEmail(id: string) {
    return api.delete(`emails/${id}`)
  },

  async getAgentActivity(agentId: string) {
    return api.get<AgentActivity[]>(`activity/agent/${agentId}`)
  },

  async getAllActivity(limit = 100) {
    return api.get<AgentActivity[]>(`activity/?limit=${limit}`)
  },

  async getEmailAccounts(userId: string) {
    return api.get<EmailAccount[]>(`email-accounts/?user_id=${userId}`)
  },

  async getEmailAccount(id: string) {
    return api.get<EmailAccount>(`email-accounts/${id}`)
  },

  async createEmailAccount(userId: string, data: CreateEmailAccountRequest) {
    return api.post<EmailAccount>(`email-accounts/?user_id=${userId}`, data)
  },

  async updateEmailAccount(id: string, data: Partial<CreateEmailAccountRequest>) {
    return api.put<EmailAccount>(`email-accounts/${id}`, data)
  },

  async deleteEmailAccount(id: string) {
    return api.delete(`email-accounts/${id}`)
  },

  async testImapConnection(data: CreateEmailAccountRequest) {
    return api.post<{ success: boolean; message: string }>('email-accounts/test-imap', data)
  },

  async testSmtpConnection(data: CreateEmailAccountRequest) {
    return api.post<{ success: boolean; message: string }>('email-accounts/test-smtp', data)
  },

  async syncEmailAccount(id: string) {
    return api.post<{ success: boolean; new_emails: number; error?: string }>(`email-accounts/${id}/sync`)
  },

  async getTemplates() {
    return api.get<AgentTemplate[]>('templates/')
  },

  async getTemplate(id: string) {
    return api.get<AgentTemplate>(`templates/${id}`)
  },

  async getHiringTemplates() {
    return api.get<AgentTemplate[]>('hiring/templates')
  },

  async getHiringTemplate(id: string) {
    return api.get<AgentTemplate>(`hiring/templates/${id}`)
  },

  async getTemplateTools(templateId: string) {
    return api.get<AgentTool[]>(`hiring/templates/${templateId}/tools`)
  },

  async getTemplatePermissions(templateId: string) {
    return api.get<Permission[]>(`hiring/templates/${templateId}/permissions`)
  },

  async getTemplateIntegrations(templateId: string) {
    return api.get<Integration[]>(`hiring/templates/${templateId}/integrations`)
  },

  async hireAgent(data: HireAgentRequest) {
    return api.post<{ message: string; agent_id: string; lifecycle_status: string }>('hiring/hire', data)
  },

  async getAgentHiringDetails(agentId: string) {
    return api.get<{ agent: AIAgent; template: AgentTemplate | null; room: OfficeRoom | null; tools: AgentTool[]; permission_details: Permission[] }>(`hiring/${agentId}/details`)
  },

  async updateAgentLifecycle(agentId: string, action: 'pause' | 'resume' | 'disable' | 'archive' | 'restart', reason?: string) {
    return api.post<{ message: string; lifecycle_status: string }>(`hiring/${agentId}/lifecycle`, { action, reason })
  },

  async deleteAgent(agentId: string) {
    return api.delete(`hiring/${agentId}`)
  },

  async getTools() {
    return api.get<AgentTool[]>('tools/')
  },

  async getToolsByCategory(category: string) {
    return api.get<AgentTool[]>(`tools/?category=${category}`)
  },

  async getToolCategories() {
    return api.get<string[]>('tools/categories')
  },

  async getTool(id: string) {
    return api.get<AgentTool>(`tools/${id}`)
  },

  async getToolWithActions(id: string) {
    return api.get<ToolWithActions>(`tools/${id}`)
  },

  async getToolsForTemplate(templateId: string) {
    return api.get<AgentTool[]>(`tools/template/${templateId}`)
  },

  async getAgentTools(agentId: string) {
    return api.get<AgentTool[]>(`tools/agent/${agentId}`)
  },

  async assignToolToAgent(agentId: string, toolId: string, config?: Record<string, unknown>) {
    return api.post(`tools/agent/${agentId}/assign`, { tool_id: toolId, config })
  },

  async removeToolFromAgent(agentId: string, toolId: string) {
    return api.delete(`tools/agent/${agentId}/remove?tool_id=${toolId}`)
  },

  async getToolAgents(toolId: string) {
    return api.get<{ id: string; name: string; role: string }[]>(`tools/${toolId}/agents`)
  },

  async validateToolAccess(agentId: string, toolName: string, actionName?: string) {
    const params = new URLSearchParams()
    if (actionName) params.append('action_name', actionName)
    return api.get<{ has_access: boolean; message: string }>(`tools/validate/${agentId}/${toolName}?${params.toString()}`)
  },

  async getPermissions() {
    return api.get<Permission[]>('permissions/')
  },

  async getPermissionsByCategory(category: string) {
    return api.get<Permission[]>(`permissions/?category=${category}`)
  },

  async getPermissionCategories() {
    return api.get<string[]>('permissions/categories')
  },

  async getPermission(id: string) {
    return api.get<Permission>(`permissions/${id}`)
  },

  async getAgentPermissions(agentId: string) {
    return api.get<AgentPermission[]>(`permissions/agent/${agentId}`)
  },

  async setAgentPermission(agentId: string, permissionId: string, accessLevel: string) {
    return api.post(`permissions/agent/${agentId}`, { permission_id: permissionId, access_level: accessLevel })
  },

  async updateAgentPermission(agentId: string, permissionId: string, data: { access_level?: string; notes?: string }) {
    return api.put(`permissions/agent/${agentId}/${permissionId}`, data)
  },

  async deleteAgentPermission(agentId: string, permissionId: string) {
    return api.delete(`permissions/agent/${agentId}/${permissionId}`)
  },

  async revokeAllAgentPermissions(agentId: string) {
    return api.post(`permissions/agent/${agentId}/revoke-all`)
  },

  async checkPermission(agentId: string, permissionName: string) {
    return api.post<{ has_permission: boolean; access_level: string; message: string; requires_approval: boolean }>(
      'permissions/check',
      { agent_id: agentId, permission_name: permissionName }
    )
  },

  async getPermissionAgents(permissionId: string) {
    return api.get<{ id: string; name: string; role: string }[]>(`permissions/${permissionId}/agents`)
  },

  async getIntegrations() {
    return api.get<Integration[]>('integrations/')
  },

  async getIntegration(id: string) {
    return api.get<Integration>(`integrations/${id}`)
  },

  async getIntegrationAccounts() {
    return api.get<IntegrationAccount[]>('integrations/accounts/')
  },

  async getIntegrationAccount(id: string) {
    return api.get<IntegrationAccount>(`integrations/accounts/${id}`)
  },

  async connectIntegration(integrationId: string, credentials: Record<string, unknown>, displayName?: string) {
    const params = new URLSearchParams({ integration_id: integrationId })
    if (displayName) params.append('display_name', displayName)
    return api.post<IntegrationAccount>(`integrations/accounts/connect?${params.toString()}`, credentials)
  },

  async disconnectIntegration(integrationId: string) {
    const params = new URLSearchParams({ integration_id: integrationId })
    return api.post(`integrations/accounts/disconnect?${params.toString()}`)
  },

  async getOAuth2AuthorizeUrl(integrationId: string) {
    return api.get<{ authorization_url: string; state: string }>(`integrations/${integrationId}/oauth2/authorize`)
  },

  async deleteIntegrationAccount(id: string) {
    return api.delete(`integrations/accounts/${id}`)
  },

  async getAgentIntegrations(agentId: string) {
    return api.get<Integration[]>(`integrations/agent/${agentId}`)
  },

  async assignIntegrationToAgent(agentId: string, integrationId: string, capabilities?: string[]) {
    const params = new URLSearchParams({ integration_id: integrationId })
    if (capabilities) {
      capabilities.forEach(c => params.append('capabilities', c))
    }
    return api.post(`integrations/agent/${agentId}/assign?${params.toString()}`)
  },

  async removeIntegrationFromAgent(agentId: string, integrationId: string) {
    const params = new URLSearchParams({ integration_id: integrationId })
    return api.delete(`integrations/agent/${agentId}/remove?${params.toString()}`)
  },

  async getIntegrationAgents(integrationId: string) {
    return api.get<{ id: string; name: string; role: string }[]>(`integrations/${integrationId}/agents`)
  },

  async getApprovals(status?: string, agentId?: string, riskLevel?: string) {
    const params = new URLSearchParams()
    if (status) params.append('status', status)
    if (agentId) params.append('agent_id', agentId)
    if (riskLevel) params.append('risk_level', riskLevel)
    const queryString = params.toString()
    return api.get<Approval[]>(`approvals/${queryString ? '?' + queryString : ''}`)
  },

  async getApproval(id: string) {
    return api.get<Approval>(`approvals/${id}`)
  },

  async getApprovalStats() {
    return api.get<ApprovalStats>('approvals/stats')
  },

  async approveApproval(id: string, notes?: string) {
    const params = notes ? `?notes=${encodeURIComponent(notes)}` : ''
    return api.post<Approval>(`approvals/${id}/approve${params}`)
  },

  async rejectApproval(id: string, notes?: string) {
    const params = notes ? `?notes=${encodeURIComponent(notes)}` : ''
    return api.post<Approval>(`approvals/${id}/reject${params}`)
  },

  async cancelApproval(id: string) {
    return api.post<Approval>(`approvals/${id}/cancel`)
  },

  async retryApproval(id: string) {
    return api.post<Approval>(`approvals/${id}/retry`)
  },

  async getApprovalEvents(id: string) {
    return api.get<{ id: string; event_type: string; old_status: string | null; new_status: string | null; description: string | null; performed_by: string | null; created_at: string | null }[]>(`approvals/${id}/events`)
  },

  async getRiskRules(activeOnly: boolean = true) {
    return api.get<RiskRule[]>(`risk-rules/?active_only=${activeOnly}`)
  },

  async getRiskRule(id: string) {
    return api.get<RiskRule>(`risk-rules/${id}`)
  },

  async getRiskSummary() {
    return api.get<RiskSummary>('risk-rules/summary')
  },

  async createRiskRule(data: Partial<RiskRule>) {
    return api.post<RiskRule>('risk-rules/', data)
  },

  async updateRiskRule(id: string, data: Partial<RiskRule>) {
    return api.put<RiskRule>(`risk-rules/${id}`, data)
  },

  async deleteRiskRule(id: string) {
    return api.delete(`risk-rules/${id}`)
  },

  async getKnowledgeSources(filters?: { category?: string; source_type?: string; status?: string; search?: string }) {
    const params = new URLSearchParams()
    if (filters?.category) params.set('category', filters.category)
    if (filters?.source_type) params.set('source_type', filters.source_type)
    if (filters?.status) params.set('status', filters.status)
    if (filters?.search) params.set('search', filters.search)
    const qs = params.toString()
    return api.get<Knowledge[]>(`knowledge/${qs ? `?${qs}` : ''}`)
  },

  async getKnowledgeSource(id: string) {
    return api.get<Knowledge>(`knowledge/${id}`)
  },

  async createKnowledgeSource(data: { name: string; description?: string; category: string; content?: string; source_type?: string; tags?: string[] }) {
    return api.post<Knowledge>('knowledge/', data)
  },

  async updateKnowledgeSource(id: string, data: Partial<Knowledge>) {
    return api.put<Knowledge>(`knowledge/${id}`, data)
  },

  async deleteKnowledgeSource(id: string) {
    return api.delete(`knowledge/${id}`)
  },

  async getKnowledgeStats() {
    return api.get<KnowledgeStats>('knowledge/stats')
  },

  async searchKnowledge(query: string, category?: string, limit?: number) {
    return api.post<{ id: string; name: string; category: string; content: string; snippet: string; score: number }[]>('knowledge/search', { query, category, limit })
  },

  async getKnowledgeAgents(knowledgeId: string) {
    return api.get<KnowledgeAgentAccess[]>(`knowledge/${knowledgeId}/agents`)
  },

  async grantKnowledgeAccess(knowledgeId: string, agentId: string, accessLevel?: string) {
    const params = accessLevel ? `?access_level=${accessLevel}` : ''
    return api.post(`knowledge/${knowledgeId}/access/${agentId}${params}`)
  },

  async revokeKnowledgeAccess(knowledgeId: string, agentId: string) {
    return api.delete(`knowledge/${knowledgeId}/access/${agentId}`)
  },

  async bulkGrantKnowledgeAccess(agentId: string, knowledgeIds: string[], accessLevel?: string) {
    return api.post('knowledge/bulk-access', { agent_id: agentId, knowledge_ids: knowledgeIds, access_level: accessLevel || 'read' })
  },

  async getAgentKnowledgeContext(agentId: string, query: string) {
    return api.get<{ context: string }>(`knowledge/agent/${agentId}/context?query=${encodeURIComponent(query)}`)
  },

  async reprocessKnowledgeEmbeddings(id: string) {
    return api.post(`knowledge/${id}/reprocess`)
  },

  async getCEOSummary() {
    return api.get<CEOSummary>('ceo/dashboard/summary')
  },

  async getCEOAgentOverview() {
    return api.get<CEOAgentOverview[]>('ceo/dashboard/agents')
  },

  async getCEOActivity(limit?: number) {
    const params = limit ? `?limit=${limit}` : ''
    return api.get<CEOActivity[]>(`ceo/dashboard/activity${params}`)
  },

  async getCEOPerformance() {
    return api.get<CEOPerformance>('ceo/dashboard/performance')
  },

  async getCEOInbox(filters?: { unread_only?: boolean; filter_type?: string; filter_priority?: string }) {
    const params = new URLSearchParams()
    if (filters?.unread_only) params.set('unread_only', 'true')
    if (filters?.filter_type) params.set('filter_type', filters.filter_type)
    if (filters?.filter_priority) params.set('filter_priority', filters.filter_priority)
    const qs = params.toString()
    return api.get<CEOInboxItem[]>(`ceo/inbox/${qs ? `?${qs}` : ''}`)
  },

  async getCEOInboxCounts() {
    return api.get<CEOInboxCounts>('ceo/inbox/counts')
  },

  async markInboxRead(notificationId: string) {
    return api.post(`ceo/inbox/${notificationId}/read`)
  },

  async markAllInboxRead() {
    return api.post('ceo/inbox/read-all')
  },

  async approveInboxItem(itemType: string, itemId: string, notes?: string) {
    return api.post(`ceo/inbox/${itemType}/${itemId}/approve`, { notes })
  },

  async rejectInboxItem(itemType: string, itemId: string, notes?: string) {
    return api.post(`ceo/inbox/${itemType}/${itemId}/reject`, { notes })
  },

  async dismissInboxItem(itemType: string, itemId: string) {
    return api.post(`ceo/inbox/${itemType}/${itemId}/dismiss`)
  },

  async archiveInboxItem(itemType: string, itemId: string) {
    return api.post(`ceo/inbox/${itemType}/${itemId}/archive`)
  },

  async resolveInboxItem(itemType: string, itemId: string) {
    return api.post(`ceo/inbox/${itemType}/${itemId}/resolve`)
  },

  async getCompanyAnalytics(days?: number) {
    const params = days ? `?days=${days}` : ''
    return api.get<CompanyAnalytics>(`analytics/company${params}`)
  },

  async getAgentRanking(days?: number) {
    const params = days ? `?days=${days}` : ''
    return api.get<AgentRankingItem[]>(`analytics/ranking${params}`)
  },

  async getDailyStats(days?: number) {
    const params = days ? `?days=${days}` : ''
    return api.get<DailyStatsItem[]>(`analytics/daily${params}`)
  },
}
