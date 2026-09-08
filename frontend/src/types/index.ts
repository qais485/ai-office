export interface User {
  id: string
  email: string
  name: string
  /** Legacy field: roles were removed — every account is a plain user. */
  role: 'user'
  is_active: boolean
  avatar_url: string | null
  created_at: string
  updated_at: string | null
}

export interface AIAgent {
  id: string
  name: string
  role: string
  description: string | null
  status: 'active' | 'inactive' | 'busy'
  room_id: string | null
  goals: string | null
  rules: string | null
  permissions: string | null
  tools: string | null
  memory_settings: string | null
  template_id: string | null
  lifecycle_status: 'draft' | 'active' | 'paused' | 'inactive' | 'error' | 'disabled' | 'archived'
  hired_at: string | null
  last_active_at: string | null
  paused_at: string | null
  disabled_at: string | null
  disabled_reason: string | null
  last_error: string | null
  archived_at: string | null
  created_at: string
  updated_at: string | null
}

export interface CreateAgentRequest {
  name: string
  role: string
  description?: string
  status?: string
  room_id?: string
  goals?: string
  rules?: string
  permissions?: string
  tools?: string
  memory_settings?: string
}

export interface UpdateAgentRequest {
  name?: string
  role?: string
  description?: string
  status?: string
  room_id?: string | null
  goals?: string
  rules?: string
  permissions?: string
  tools?: string
  memory_settings?: string
}

export interface OfficeRoom {
  id: string
  name: string
  description: string | null
  status: 'available' | 'occupied' | 'maintenance'
  room_type: string | null
  capacity: string
  created_at: string
  updated_at: string | null
}

export interface CreateRoomRequest {
  name: string
  description?: string
  status?: string
  room_type?: string
  capacity?: string
}

export interface Task {
  id: string
  title: string
  description: string
  status: 'pending' | 'running' | 'waiting_approval' | 'completed' | 'failed' | 'cancelled'
  task_type: 'tool_execution' | 'agent_collaboration' | 'approval_required' | 'general'
  agent_id: string
  agent_name: string | null
  assigned_by: string
  assigned_to_agent_id: string | null
  result?: string
  priority: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  input_json: Record<string, unknown> | null
  output_json: Record<string, unknown> | null
  parent_task_id: string | null
  approval_id: string | null
  tool_name: string | null
  tool_action: string | null
  created_at: string
  updated_at: string | null
}

export interface TaskStats {
  total: number
  pending: number
  running: number
  completed: number
  failed: number
  cancelled: number
  waiting_approval: number
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  message?: string
  error?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface UpdateProfileRequest {
  name: string
}

export interface AgentSummary {
  id: string
  name: string
  role: string
  status: 'active' | 'inactive' | 'busy'
  room_name: string | null
}

export interface TaskSummary {
  id: string
  title: string
  status: 'pending' | 'running' | 'waiting_approval' | 'completed' | 'failed' | 'cancelled'
  priority: string
  agent_name: string
  created_at: string
}

export interface DashboardSummary {
  total_agents: number
  active_agents: number
  busy_agents: number
  inactive_agents: number

  total_rooms: number
  available_rooms: number
  occupied_rooms: number
  maintenance_rooms: number

  total_tasks: number
  pending_tasks: number
  in_progress_tasks: number
  completed_tasks: number
  failed_tasks: number

  agents: AgentSummary[]
  recent_tasks: TaskSummary[]
  pending_actions: TaskSummary[]
}

export interface EmailMessage {
  id: string
  from_address: string
  to_address: string
  subject: string
  body: string
  status: 'new' | 'processing' | 'replied' | 'escalated' | 'failed'
  agent_id: string | null
  conversation_id: string | null
  draft_response: string | null
  category: string | null
  account_id: string | null
  created_at: string
  updated_at: string | null
}

export interface CreateEmailRequest {
  from_address: string
  to_address: string
  subject: string
  body: string
  agent_id?: string
  conversation_id?: string
  category?: string
  account_id?: string
}

export interface EmailStats {
  total: number
  new: number
  processing: number
  replied: number
  escalated: number
  failed: number
}

export interface AgentActivity {
  id: string
  agent_id: string
  activity_type: string
  description: string | null
  metadata_json: Record<string, unknown> | null
  task_id: string | null
  tool_name: string | null
  status: string | null
  created_at: string
  updated_at: string | null
}

export interface EmailAccount {
  id: string
  user_id: string
  email_address: string
  display_name: string | null
  imap_host: string
  imap_port: number
  imap_username: string
  imap_use_ssl: boolean
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_use_ssl: boolean
  is_active: boolean
  last_sync_at: string | null
  sync_error: string | null
  sync_frequency_minutes: number
  created_at: string
  updated_at: string | null
}

export interface CreateEmailAccountRequest {
  email_address: string
  display_name?: string
  imap_host: string
  imap_port?: number
  imap_username: string
  imap_password: string
  imap_use_ssl?: boolean
  smtp_host: string
  smtp_port?: number
  smtp_username: string
  smtp_password: string
  smtp_use_ssl?: boolean
  sync_frequency_minutes?: number
}

export interface AgentTemplate {
  id: string
  name: string
  role: string
  description: string | null
  default_goals: string[] | null
  default_rules: string[] | null
  default_permissions: string[] | null
  default_tools: string[] | null
  default_knowledge: string[] | null
  icon_url: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface HireAgentRequest {
  template_id: string
  name: string
  description?: string
  room_id?: string
  tool_ids?: string[]
  permission_ids?: string[]
  integration_ids?: string[]
  auto_create_room?: boolean
}

export interface ToolAction {
  id: string
  tool_id: string
  name: string
  display_name: string
  description: string | null
  risk_level: string
  requires_approval: boolean
  input_schema: Record<string, unknown> | null
  output_schema: Record<string, unknown> | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface ToolPermission {
  id: string
  tool_id: string
  action_id: string | null
  permission_id: string
  is_required: boolean
  created_at: string
}

export interface AgentToolAssignment {
  id: string
  agent_id: string
  tool_id: string
  is_enabled: boolean
  config: Record<string, unknown> | null
  created_at: string
}

export interface AgentTool {
  id: string
  name: string
  display_name: string
  description: string | null
  category: string
  integration_id: string | null
  input_schema: Record<string, unknown> | null
  output_schema: Record<string, unknown> | null
  risk_level: string
  requires_approval: boolean
  is_active: boolean
  version: string
  created_at: string
  updated_at: string | null
}

export interface ToolWithActions extends AgentTool {
  actions: ToolAction[]
  permissions: ToolPermission[]
}

export interface Permission {
  id: string
  name: string
  description: string | null
  category: string
  risk_level: string
  default_approval_required: boolean
  created_at: string
}

export interface AgentPermission {
  id: string
  agent_id: string
  permission_id: string
  access_level: string
  conditions: Record<string, unknown> | null
  granted_by: string | null
  notes: string | null
  created_at: string
  updated_at: string | null
  permission_name: string
  permission_description: string | null
  permission_category: string
  permission_risk_level: string
}

export interface Integration {
  id: string
  name: string
  display_name: string
  description: string | null
  icon_url: string | null
  auth_type: string
  config_schema: Record<string, unknown> | null
  capabilities: Record<string, unknown> | null
  is_active: boolean
  oauth2_authorize_url: string | null
  oauth2_token_url: string | null
  oauth2_client_id_key: string | null
  oauth2_client_secret_key: string | null
  oauth2_scopes: string | null
  oauth2_redirect_path: string | null
  created_at: string
  updated_at: string | null
}

export interface IntegrationAccount {
  id: string
  user_id: string
  integration_id: string
  display_name: string | null
  credentials: Record<string, unknown> | null
  config: Record<string, unknown> | null
  status: string
  last_sync_at: string | null
  oauth2_token_expiry: string | null
  oauth2_scope: string | null
  created_at: string
  updated_at: string | null
}

// Instagram-specific fields stored inside IntegrationAccount.config
export interface InstagramAccountConfig {
  instagram_user_id?: string
  username?: string
  name?: string
  account_type?: string
  media_count?: number
  facebook_page_id?: string
  facebook_page_name?: string
  connected_via?: string
  detected_at?: string
}

export interface Notification {
  id: string
  user_id: string
  agent_id: string | null
  title: string
  message: string
  type: string
  is_read: boolean
  created_at: string
}

export interface Approval {
  id: string
  agent_id: string
  agent_name?: string
  agent_role?: string
  action: string
  description: string | null
  parameters: Record<string, unknown> | null
  reason: string | null
  risk_level: string
  status: 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled'
  requested_at: string
  decided_at: string | null
  decided_by: string | null
  decided_by_name?: string | null
  decision_notes: string | null
  created_at: string
}

export interface ApprovalStats {
  pending: number
  approved: number
  rejected: number
  expired: number
  cancelled: number
  total: number
}

export interface AuditLog {
  id: string
  user_id: string | null
  agent_id: string | null
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

export interface Knowledge {
  id: string
  name: string
  description: string | null
  category: string
  content: string | null
  source_type: 'pdf' | 'document' | 'text' | 'url' | 'note' | 'faq'
  status: 'active' | 'processing' | 'inactive' | 'error'
  file_path: string | null
  tags: string[] | null
  chunk_count: string | null
  embedding_id: string | null
  created_by: string | null
  created_at: string
  updated_at: string | null
}

export interface KnowledgeAgentAccess {
  agent_id: string
  agent_name: string
  access_level: string
  granted_by: string | null
}

export interface KnowledgeStats {
  total: number
  active: number
  processing: number
  error: number
  by_category: Record<string, number>
  agents_with_access: number
}

export interface AgentActivityLog {
  id: string
  agent_id: string
  agent_name: string
  activity_type: string
  description: string | null
  tool_name: string | null
  status: string | null
  created_at: string
}

export interface RiskRule {
  id: string
  name: string
  description: string | null
  action_name: string | null
  tool_id: string | null
  risk_level: string
  requires_approval: boolean
  conditions: Record<string, unknown> | null
  priority: number
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface RiskSummary {
  total_rules: number
  active_rules: number
  by_risk_level: {
    low: number
    medium: number
    high: number
    critical: number
  }
  approval_required: number
}

export interface CEOSummary {
  agents: {
    total: number
    active: number
    inactive: number
    error: number
  }
  tasks: {
    total: number
    today: number
    completed: number
    running: number
    failed: number
    success_rate: number
  }
  approvals: {
    pending: number
  }
  emails: {
    today: number
  }
  rooms: {
    total: number
  }
}

export interface CEOAgentOverview {
  id: string
  name: string
  role: string
  status: string
  lifecycle_status: string | null
  room: { id: string; name: string } | null
  current_task: { id: string; title: string; status: string } | null
  tasks: { pending: number; completed: number; failed: number }
  last_active_at: string | null
  last_error: string | null
}

export interface CEOActivity {
  id: string
  agent_id: string
  agent_name: string
  activity_type: string
  description: string
  tool_name: string | null
  status: string | null
  created_at: string
}

export interface CEOPerformance {
  overall: {
    total_tasks: number
    completed: number
    failed: number
    success_rate: number
  }
  by_agent: Array<{
    agent_id: string
    agent_name: string
    role: string
    total_tasks: number
    completed: number
    failed: number
    success_rate: number
  }>
}

export interface CEOInboxItem {
  type: 'approval' | 'agent_error' | 'failed_task' | 'pending_task' | 'notification' | 'system_alert'
  id: string
  title: string
  message: string
  risk_level?: string
  agent_name?: string
  agent_id?: string
  notification_type?: string
  status: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  is_read?: boolean
  reference_type?: string
  reference_id?: string | null
  created_at: string
  expires_soon?: boolean
  parameters?: Record<string, unknown>
  reason?: string
  error_detail?: string
}

export interface CEOInboxCounts {
  pending_approvals: number
  error_agents: number
  failed_tasks: number
  unread_notifications: number
  system_alerts: number
  total: number
}

export interface CompanyAnalytics {
  period_days: number
  total_agents: number
  total_tasks_completed: number
  total_tasks_failed: number
  success_rate: number
  total_activities: number
  pending_approvals: number
}

export interface AgentRankingItem {
  agent_id: string
  agent_name: string
  tasks_completed: number
  success_rate: number
}

export interface DailyStatsItem {
  date: string
  tasks_completed: number
  tasks_failed: number
  activities_count: number
}
