import { useState, useEffect, useCallback } from 'react'
import type { CEOSummary, CEOAgentOverview, CEOActivity, CEOPerformance, CEOInboxItem, CEOInboxCounts } from '../types'
import { officeService } from '../services/office'
import { useAuthStore } from '../stores/useAuthStore'

const STATUS_DOT: Record<string, string> = {
  active: 'bg-green-500',
  busy: 'bg-amber-500',
  inactive: 'bg-gray-400',
  error: 'bg-red-500',
  paused: 'bg-yellow-500',
  disabled: 'bg-red-400',
}

const LIFECYCLE_DOT: Record<string, string> = {
  active: 'bg-green-500',
  paused: 'bg-yellow-500',
  inactive: 'bg-gray-400',
  error: 'bg-red-500',
  disabled: 'bg-red-400',
  draft: 'bg-gray-300',
  archived: 'bg-gray-300',
}

const INBOX_TYPE_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  approval: { icon: '⏳', label: 'Approval', color: 'bg-purple-100 text-purple-700' },
  agent_error: { icon: '🔴', label: 'Agent Error', color: 'bg-red-100 text-red-700' },
  failed_task: { icon: '❌', label: 'Failed Task', color: 'bg-red-100 text-red-700' },
  pending_task: { icon: '📋', label: 'Pending Task', color: 'bg-blue-100 text-blue-700' },
  notification: { icon: '🔔', label: 'Notification', color: 'bg-gray-100 text-gray-600' },
  system_alert: { icon: '⚠️', label: 'System Alert', color: 'bg-amber-100 text-amber-700' },
}

const PRIORITY_CONFIG: Record<string, { label: string; color: string; border: string; dot: string }> = {
  critical: { label: 'Critical', color: 'bg-red-100 text-red-700', border: 'border-l-red-500', dot: 'bg-red-500' },
  high: { label: 'High', color: 'bg-orange-100 text-orange-700', border: 'border-l-orange-500', dot: 'bg-orange-500' },
  medium: { label: 'Medium', color: 'bg-amber-100 text-amber-700', border: 'border-l-amber-400', dot: 'bg-amber-400' },
  low: { label: 'Low', color: 'bg-gray-100 text-gray-600', border: 'border-l-gray-300', dot: 'bg-gray-400' },
}

function StatCard({ label, value, sub, color }: { label: string; value: number | string; sub?: string; color: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function AgentCard({ agent }: { agent: CEOAgentOverview }) {
  const dot = STATUS_DOT[agent.status] || 'bg-gray-400'
  const lifecycleDot = LIFECYCLE_DOT[agent.lifecycle_status || ''] || 'bg-gray-400'

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${dot}`} />
          <div>
            <div className="font-semibold text-gray-900 text-sm">{agent.name}</div>
            <div className="text-xs text-gray-500">{agent.role}</div>
          </div>
        </div>
        <span className={`w-2 h-2 rounded-full ${lifecycleDot}`} title={agent.lifecycle_status || ''} />
      </div>

      {agent.current_task ? (
        <div className="bg-amber-50 rounded-lg px-3 py-2 mb-2">
          <div className="text-[11px] text-amber-600 font-medium">Current Task</div>
          <div className="text-xs text-gray-700 truncate">{agent.current_task.title}</div>
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg px-3 py-2 mb-2">
          <div className="text-xs text-gray-400">No active task</div>
        </div>
      )}

      {agent.room && (
        <div className="text-xs text-gray-500 mb-2">📍 {agent.room.name}</div>
      )}

      <div className="flex items-center gap-3 text-xs text-gray-500">
        <span>✓ {agent.tasks.completed}</span>
        <span>⏳ {agent.tasks.pending}</span>
        {agent.tasks.failed > 0 && <span className="text-red-500">✗ {agent.tasks.failed}</span>}
      </div>

      {agent.last_error && (
        <div className="mt-2 bg-red-50 rounded-lg px-3 py-1.5">
          <div className="text-[11px] text-red-600 truncate">{agent.last_error}</div>
        </div>
      )}
    </div>
  )
}

function ActivityItem({ activity }: { activity: CEOActivity }) {
  const timeAgo = getTimeAgo(activity.created_at)
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0">
      <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-xs font-medium text-primary-700 shrink-0">
        {activity.agent_name?.charAt(0) || '?'}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-gray-900">
          <span className="font-medium">{activity.agent_name}</span>
          <span className="text-gray-500 mx-1">·</span>
          <span className="text-gray-600">{activity.description || activity.activity_type}</span>
        </div>
        {activity.tool_name && (
          <div className="text-xs text-gray-400 mt-0.5">using {activity.tool_name}</div>
        )}
      </div>
      <span className="text-xs text-gray-400 shrink-0">{timeAgo}</span>
    </div>
  )
}

function InboxCard({ item, onApprove, onReject, onDismiss }: {
  item: CEOInboxItem
  onApprove: (item: CEOInboxItem) => void
  onReject: (item: CEOInboxItem) => void
  onDismiss: (item: CEOInboxItem) => void
}) {
  const typeConfig = INBOX_TYPE_CONFIG[item.type] || INBOX_TYPE_CONFIG.notification
  const priorityConfig = PRIORITY_CONFIG[item.priority] || PRIORITY_CONFIG.low
  const isApproval = item.type === 'approval'
  const isFailed = item.type === 'failed_task'
  const isNotification = item.type === 'notification'

  return (
    <div className={`border-l-4 ${priorityConfig.border} bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center text-lg" style={{ backgroundColor: 'transparent' }}>
            {typeConfig.icon}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{item.title}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeConfig.color}`}>
                {typeConfig.label}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${priorityConfig.color}`}>
                {priorityConfig.label}
              </span>
              {item.expires_soon && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                  Expires Soon
                </span>
              )}
            </div>
          </div>
        </div>
        <span className="text-xs text-gray-400">{getTimeAgo(item.created_at)}</span>
      </div>

      <p className="text-sm text-gray-600 mb-3">{item.message}</p>

      <div className="flex items-center gap-4 text-xs text-gray-500 mb-3">
        {item.agent_name && (
          <div className="flex items-center gap-1">
            <span className="font-medium text-gray-700">{item.agent_name}</span>
          </div>
        )}
        {item.risk_level && (
          <span className={`px-1.5 py-0.5 rounded ${
            item.risk_level === 'critical' ? 'bg-red-100 text-red-700' :
            item.risk_level === 'high' ? 'bg-orange-100 text-orange-700' :
            item.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' :
            'bg-gray-100 text-gray-600'
          }`}>{item.risk_level} risk</span>
        )}
        {item.reason && (
          <span className="text-gray-400">Reason: {item.reason}</span>
        )}
      </div>

      {item.error_detail && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-3">
          <p className="text-xs text-red-700">{item.error_detail}</p>
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${priorityConfig.dot}`} />
          <span className="text-xs text-gray-400">{new Date(item.created_at).toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-2">
          {isApproval && (
            <>
              <button
                onClick={() => onApprove(item)}
                className="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-lg hover:bg-green-700 transition-colors"
              >
                Approve
              </button>
              <button
                onClick={() => onReject(item)}
                className="px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 transition-colors"
              >
                Reject
              </button>
            </>
          )}
          {isFailed && (
            <button
              onClick={() => onDismiss(item)}
              className="px-3 py-1.5 bg-gray-200 text-gray-700 text-xs font-medium rounded-lg hover:bg-gray-300 transition-colors"
            >
              Dismiss
            </button>
          )}
          {isNotification && !item.is_read && (
            <button
              onClick={() => onDismiss(item)}
              className="px-3 py-1.5 bg-gray-200 text-gray-700 text-xs font-medium rounded-lg hover:bg-gray-300 transition-colors"
            >
              Mark Read
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function getTimeAgo(dateStr: string): string {
  if (!dateStr) return ''
  try {
    const now = Date.now()
    const then = new Date(dateStr).getTime()
    if (isNaN(then)) return ''
    const diff = now - then
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    return `${days}d ago`
  } catch {
    return ''
  }
}

export default function CEOPage() {
  const user = useAuthStore((s) => s.user)
  const [summary, setSummary] = useState<CEOSummary | null>(null)
  const [agents, setAgents] = useState<CEOAgentOverview[]>([])
  const [activity, setActivity] = useState<CEOActivity[]>([])
  const [performance, setPerformance] = useState<CEOPerformance | null>(null)
  const [inbox, setInbox] = useState<CEOInboxItem[]>([])
  const [inboxCounts, setInboxCounts] = useState<CEOInboxCounts | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'overview' | 'inbox' | 'agents' | 'activity' | 'performance'>('overview')
  const [inboxTypeFilter, setInboxTypeFilter] = useState<string | null>(null)
  const [inboxPriorityFilter, setInboxPriorityFilter] = useState<string | null>(null)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    try {
      setLoading(true)
      const [sumRes, agentsRes, actRes, perfRes, inboxRes, countsRes] = await Promise.all([
        officeService.getCEOSummary(),
        officeService.getCEOAgentOverview(),
        officeService.getCEOActivity(15),
        officeService.getCEOPerformance(),
        officeService.getCEOInbox(),
        officeService.getCEOInboxCounts(),
      ])
      setSummary(sumRes.data ?? null)
      setAgents(agentsRes.data ?? [])
      setActivity(actRes.data ?? [])
      setPerformance(perfRes.data ?? null)
      setInbox(inboxRes.data ?? [])
      setInboxCounts(countsRes.data ?? null)
    } catch (err) {
      console.error('Failed to load CEO dashboard:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadInbox = useCallback(async () => {
    try {
      const [inboxRes, countsRes] = await Promise.all([
        officeService.getCEOInbox({
          filter_type: inboxTypeFilter || undefined,
          filter_priority: inboxPriorityFilter || undefined,
        }),
        officeService.getCEOInboxCounts(),
      ])
      setInbox(inboxRes.data ?? [])
      setInboxCounts(countsRes.data ?? null)
    } catch (err) {
      console.error('Failed to load inbox:', err)
    }
  }, [inboxTypeFilter, inboxPriorityFilter])

  useEffect(() => {
    if (activeTab === 'inbox') {
      loadInbox()
    }
  }, [activeTab, loadInbox])

  const handleApprove = async (item: CEOInboxItem) => {
    try {
      await officeService.approveInboxItem(item.type, item.id, 'Approved from CEO Inbox')
      await loadInbox()
      await loadAll()
    } catch (err) {
      console.error('Failed to approve:', err)
    }
  }

  const handleReject = async (item: CEOInboxItem) => {
    try {
      await officeService.rejectInboxItem(item.type, item.id, 'Rejected from CEO Inbox')
      await loadInbox()
      await loadAll()
    } catch (err) {
      console.error('Failed to reject:', err)
    }
  }

  const handleDismiss = async (item: CEOInboxItem) => {
    try {
      await officeService.dismissInboxItem(item.type, item.id)
      await loadInbox()
    } catch (err) {
      console.error('Failed to dismiss:', err)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await officeService.markAllInboxRead()
      await loadInbox()
    } catch (err) {
      console.error('Failed to mark all read:', err)
    }
  }

  if (loading && !summary) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  const tabs = [
    { key: 'overview' as const, label: 'Overview' },
    { key: 'inbox' as const, label: 'Inbox', badge: inboxCounts?.total || 0 },
    { key: 'agents' as const, label: 'Agents' },
    { key: 'activity' as const, label: 'Activity' },
    { key: 'performance' as const, label: 'Performance' },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">CEO Dashboard</h1>
            <p className="text-gray-500 mt-1">Welcome back, {user?.name || 'CEO'}</p>
          </div>
          <button onClick={loadAll}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Total Agents" value={summary.agents.total} sub={`${summary.agents.active} active`} color="text-gray-900" />
          <StatCard label="Active Agents" value={summary.agents.active} color="text-green-600" />
          <StatCard label="Errors" value={summary.agents.error} color={summary.agents.error > 0 ? 'text-red-600' : 'text-gray-900'} />
          <StatCard label="Tasks Today" value={summary.tasks.today} sub={`${summary.tasks.running} running`} color="text-blue-600" />
          <StatCard label="Success Rate" value={`${summary.tasks.success_rate}%`} sub={`${summary.tasks.completed} done`} color="text-emerald-600" />
          <StatCard label="Pending Approvals" value={summary.approvals.pending} color={summary.approvals.pending > 0 ? 'text-amber-600' : 'text-gray-900'} />
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 mb-6 border-b border-gray-200">
        {tabs.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors relative ${
              activeTab === tab.key
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            {tab.label}
            {typeof tab.badge === 'number' && tab.badge > 0 && (
              <span className="absolute -top-0.5 -right-1 px-1.5 py-0.5 text-[10px] font-bold bg-red-500 text-white rounded-full min-w-[18px] text-center">
                {tab.badge > 99 ? '99+' : tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-900">Agent Status</h2>
              <button onClick={() => setActiveTab('agents')} className="text-xs text-primary-600 hover:text-primary-700">View all →</button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {agents.slice(0, 4).map((agent) => (
                <AgentCard key={agent.id} agent={agent} />
              ))}
            </div>
            {agents.length === 0 && <div className="text-center py-8 text-gray-500 text-sm">No agents yet</div>}
          </div>

          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-900">
                Attention Needed
                {inboxCounts && inboxCounts.total > 0 && (
                  <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">{inboxCounts.total}</span>
                )}
              </h2>
              <button onClick={() => setActiveTab('inbox')} className="text-xs text-primary-600 hover:text-primary-700">View all →</button>
            </div>
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {inbox.slice(0, 6).map((item, i) => (
                <div key={`${item.type}-${item.id}-${i}`} className={`border-l-4 ${PRIORITY_CONFIG[item.priority]?.border || 'border-l-gray-300'} bg-white rounded-r-lg px-4 py-3 hover:bg-gray-50 transition-colors`}>
                  <div className="flex items-start gap-2">
                    <span className="text-sm mt-0.5">{INBOX_TYPE_CONFIG[item.type]?.icon || '📬'}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">{item.title}</div>
                      <div className="text-xs text-gray-500 truncate mt-0.5">{item.message}</div>
                    </div>
                  </div>
                </div>
              ))}
              {inbox.length === 0 && <div className="text-center py-8 text-gray-500 text-sm">All clear!</div>}
            </div>
          </div>
        </div>
      )}

      {/* Inbox Tab */}
      {activeTab === 'inbox' && (
        <div>
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="flex gap-2">
                <span className="text-sm text-gray-500 py-1.5">Type:</span>
                {Object.entries(INBOX_TYPE_CONFIG).map(([key, config]) => (
                  <button key={key} onClick={() => setInboxTypeFilter(inboxTypeFilter === key ? null : key)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      inboxTypeFilter === key ? `${config.color}` : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}>
                    {config.icon} {config.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex gap-2">
                <span className="text-sm text-gray-500 py-1.5">Priority:</span>
                {Object.entries(PRIORITY_CONFIG).map(([key, config]) => (
                  <button key={key} onClick={() => setInboxPriorityFilter(inboxPriorityFilter === key ? null : key)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      inboxPriorityFilter === key ? `${config.color}` : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}>
                    {config.label}
                  </button>
                ))}
              </div>
              <button onClick={handleMarkAllRead}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors">
                Mark All Read
              </button>
            </div>
          </div>

          {inboxCounts && (
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
              <button onClick={() => setInboxTypeFilter(null)}
                className={`p-3 rounded-xl border text-left transition-colors ${!inboxTypeFilter ? 'bg-primary-50 border-primary-200' : 'bg-white border-gray-200 hover:border-gray-300'}`}>
                <div className="text-lg font-bold text-gray-900">{inboxCounts.total}</div>
                <div className="text-xs text-gray-500">All Items</div>
              </button>
              <button onClick={() => setInboxTypeFilter(inboxTypeFilter === 'approval' ? null : 'approval')}
                className={`p-3 rounded-xl border text-left transition-colors ${inboxTypeFilter === 'approval' ? 'bg-purple-50 border-purple-200' : 'bg-white border-gray-200 hover:border-gray-300'}`}>
                <div className="text-lg font-bold text-purple-600">{inboxCounts.pending_approvals}</div>
                <div className="text-xs text-gray-500">Approvals</div>
              </button>
              <button onClick={() => setInboxTypeFilter(inboxTypeFilter === 'agent_error' ? null : 'agent_error')}
                className={`p-3 rounded-xl border text-left transition-colors ${inboxTypeFilter === 'agent_error' ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200 hover:border-gray-300'}`}>
                <div className="text-lg font-bold text-red-600">{inboxCounts.error_agents}</div>
                <div className="text-xs text-gray-500">Agent Errors</div>
              </button>
              <button onClick={() => setInboxTypeFilter(inboxTypeFilter === 'failed_task' ? null : 'failed_task')}
                className={`p-3 rounded-xl border text-left transition-colors ${inboxTypeFilter === 'failed_task' ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200 hover:border-gray-300'}`}>
                <div className="text-lg font-bold text-red-600">{inboxCounts.failed_tasks}</div>
                <div className="text-xs text-gray-500">Failed Tasks</div>
              </button>
              <button onClick={() => setInboxTypeFilter(inboxTypeFilter === 'system_alert' ? null : 'system_alert')}
                className={`p-3 rounded-xl border text-left transition-colors ${inboxTypeFilter === 'system_alert' ? 'bg-amber-50 border-amber-200' : 'bg-white border-gray-200 hover:border-gray-300'}`}>
                <div className="text-lg font-bold text-amber-600">{inboxCounts.system_alerts}</div>
                <div className="text-xs text-gray-500">System Alerts</div>
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {inbox.map((item, i) => (
              <InboxCard
                key={`${item.type}-${item.id}-${i}`}
                item={item}
                onApprove={handleApprove}
                onReject={handleReject}
                onDismiss={handleDismiss}
              />
            ))}
          </div>

          {inbox.length === 0 && (
            <div className="text-center py-12">
              <div className="text-4xl mb-3">✅</div>
              <p className="text-gray-500 text-lg font-medium">All clear!</p>
              <p className="text-gray-400 text-sm mt-1">No items match your filters</p>
            </div>
          )}
        </div>
      )}

      {/* Agents Tab */}
      {activeTab === 'agents' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
          {agents.length === 0 && <div className="col-span-full text-center py-12 text-gray-500">No agents</div>}
        </div>
      )}

      {/* Activity Tab */}
      {activeTab === 'activity' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Recent Activity</h2>
          <div className="divide-y divide-gray-100">
            {activity.map((item) => (
              <ActivityItem key={item.id} activity={item} />
            ))}
          </div>
          {activity.length === 0 && <div className="text-center py-8 text-gray-500 text-sm">No activity yet</div>}
        </div>
      )}

      {/* Performance Tab */}
      {activeTab === 'performance' && performance && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Overall Performance</h2>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{performance.overall.total_tasks}</div>
                <div className="text-xs text-gray-500">Total Tasks</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{performance.overall.completed}</div>
                <div className="text-xs text-gray-500">Completed</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">{performance.overall.failed}</div>
                <div className="text-xs text-gray-500">Failed</div>
              </div>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Success Rate</span>
                <span className="text-lg font-bold text-emerald-600">{performance.overall.success_rate}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div className="bg-emerald-500 h-3 rounded-full transition-all" style={{ width: `${performance.overall.success_rate}%` }} />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Agent Performance</h2>
            <div className="space-y-3">
              {performance.by_agent.slice(0, 8).map((agent) => (
                <div key={agent.agent_id} className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-xs font-medium text-primary-700 shrink-0">
                    {agent.agent_name.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900 truncate">{agent.agent_name}</span>
                      <span className="text-xs text-gray-500">{agent.success_rate}%</span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                        <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: `${agent.success_rate}%` }} />
                      </div>
                      <span className="text-[11px] text-gray-400">{agent.completed}/{agent.total_tasks}</span>
                    </div>
                  </div>
                </div>
              ))}
              {performance.by_agent.length === 0 && <div className="text-center py-4 text-gray-500 text-sm">No agent data</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
