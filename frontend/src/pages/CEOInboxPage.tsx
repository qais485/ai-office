import { useState, useEffect, useCallback } from 'react'
import type { CEOInboxItem, CEOInboxCounts } from '../types'
import { officeService } from '../services/office'
import { useRealtimeStore } from '../stores/useRealtimeStore'

const TYPE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  approval: { label: 'Approval', icon: 'â³', color: 'bg-amber-500/15 text-amber-300' },
  agent_error: { label: 'Agent Error', icon: 'ðŸ”´', color: 'bg-red-500/15 text-red-300' },
  failed_task: { label: 'Failed Task', icon: 'âŒ', color: 'bg-red-500/15 text-red-300' },
  pending_task: { label: 'Pending Task', icon: 'ðŸ“‹', color: 'bg-blue-500/15 text-blue-300' },
  notification: { label: 'Notification', icon: 'ðŸ””', color: 'bg-white/10 text-white/70' },
  system_alert: { label: 'System Alert', icon: 'âš ï¸', color: 'bg-orange-500/15 text-orange-300' },
}

const PRIORITY_CONFIG: Record<string, { label: string; color: string; border: string; dot: string }> = {
  critical: { label: 'Critical', color: 'bg-red-500/15 text-red-300', border: 'border-l-red-500', dot: 'bg-red-500' },
  high: { label: 'High', color: 'bg-orange-500/15 text-orange-300', border: 'border-l-orange-500', dot: 'bg-orange-500' },
  medium: { label: 'Medium', color: 'bg-amber-500/15 text-amber-300', border: 'border-l-amber-400', dot: 'bg-amber-400' },
  low: { label: 'Low', color: 'bg-white/10 text-white/70', border: 'border-l-white/20', dot: 'bg-white/30' },
}

function getTimeAgo(dateStr: string): string {
  if (!dateStr) return ''
  try {
    const diff = Date.now() - new Date(dateStr).getTime()
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

function InboxItemCard({ item, onApprove, onReject, onDismiss, onArchive, onResolve }: {
  item: CEOInboxItem
  onApprove: (item: CEOInboxItem) => void
  onReject: (item: CEOInboxItem) => void
  onDismiss: (item: CEOInboxItem) => void
  onArchive: (item: CEOInboxItem) => void
  onResolve: (item: CEOInboxItem) => void
}) {
  const typeConfig = TYPE_CONFIG[item.type] || TYPE_CONFIG.notification
  const priorityConfig = PRIORITY_CONFIG[item.priority] || PRIORITY_CONFIG.low
  const isApproval = item.type === 'approval'
  const isFailed = item.type === 'failed_task'
  const isError = item.type === 'agent_error'
  const isNotification = item.type === 'notification'

  return (
    <div className={`border-l-4 ${priorityConfig.border} bg-white/[0.03] rounded-xl border border-white/10 p-5 hover:bg-white/[0.05] hover:border-white/15 transition-colors`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center text-lg">
            {typeConfig.icon}
          </div>
          <div>
            <h3 className="font-semibold text-white text-sm">{item.title}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeConfig.color}`}>
                {typeConfig.label}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${priorityConfig.color}`}>
                {priorityConfig.label}
              </span>
              {item.expires_soon && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-500/15 text-red-300 animate-pulse">
                  Expires Soon
                </span>
              )}
              {item.is_read && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-white/10 text-white/50">
                  Read
                </span>
              )}
            </div>
          </div>
        </div>
        <span className="text-xs text-white/40">{getTimeAgo(item.created_at)}</span>
      </div>

      <p className="text-sm text-white/70 mb-3">{item.message}</p>

      <div className="flex items-center gap-3 text-xs text-white/50 mb-3">
        {item.agent_name && (
          <span className="flex items-center gap-1">
            <span className="w-5 h-5 rounded-full bg-indigo-500/20 flex items-center justify-center text-[10px] font-medium text-indigo-300">
              {item.agent_name.charAt(0)}
            </span>
            <span className="font-medium text-white/80">{item.agent_name}</span>
          </span>
        )}
        {item.risk_level && (
          <span className={`px-1.5 py-0.5 rounded ${
            item.risk_level === 'critical' ? 'bg-red-500/15 text-red-300' :
            item.risk_level === 'high' ? 'bg-orange-500/15 text-orange-300' :
            item.risk_level === 'medium' ? 'bg-amber-500/15 text-amber-300' :
            'bg-white/10 text-white/70'
          }`}>{item.risk_level} risk</span>
        )}
        {item.reason && (
          <span className="text-white/40 truncate">Reason: {item.reason}</span>
        )}
      </div>

      {item.error_detail && (
        <div className="bg-red-500/10 border border-red-500/25 rounded-lg p-3 mb-3">
          <p className="text-xs text-red-700">{item.error_detail}</p>
        </div>
      )}

      {item.parameters && Object.keys(item.parameters).length > 0 && (
        <div className="bg-white/[0.04] rounded-lg p-3 mb-3">
          <p className="text-[11px] text-white/50 font-medium mb-1">Parameters</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(item.parameters).map(([key, val]) => (
              <span key={key} className="text-xs bg-white/5 border border-white/10 rounded px-2 py-0.5">
                <span className="font-medium text-white/70">{key}:</span> <span className="text-white/80">{String(val)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-white/6">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${priorityConfig.dot}`} />
          <span className="text-xs text-white/40">{new Date(item.created_at).toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-2">
          {isApproval && (
            <>
              <button onClick={() => onApprove(item)}
                className="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-lg hover:bg-green-700 transition-colors">
                Approve
              </button>
              <button onClick={() => onReject(item)}
                className="px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 transition-colors">
                Reject
              </button>
            </>
          )}
          {(isFailed || isError) && (
            <button onClick={() => onResolve(item)}
              className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded-lg hover:bg-indigo-500 transition-colors">
              Resolve
            </button>
          )}
          {isNotification && !item.is_read && (
            <button onClick={() => onDismiss(item)}
              className="px-3 py-1.5 bg-white/10 text-white/80 text-xs font-medium rounded-lg hover:bg-white/15 transition-colors">
              Dismiss
            </button>
          )}
          <button onClick={() => onArchive(item)}
            className="px-3 py-1.5 bg-white/10 text-white/70 text-xs font-medium rounded-lg hover:bg-white/15 transition-colors">
            Archive
          </button>
        </div>
      </div>
    </div>
  )
}

export default function CEOInboxPage() {
  const [items, setItems] = useState<CEOInboxItem[]>([])
  const [counts, setCounts] = useState<CEOInboxCounts | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState<string | null>(null)
  const [filterPriority, setFilterPriority] = useState<string | null>(null)
  const [unreadOnly, setUnreadOnly] = useState(false)

  useEffect(() => {
    loadInbox()
  }, [filterType, filterPriority, unreadOnly])

  // Real-time: auto-refresh inbox when relevant events arrive
  const debouncedRefresh = useCallback(() => {
    const timer = setTimeout(() => loadInbox(), 500)
    return () => clearTimeout(timer)
  }, [filterType, filterPriority, unreadOnly])

  useEffect(() => {
    const events = [
      'approval_created', 'approval_approved', 'approval_rejected',
      'agent_error', 'agent_lifecycle_changed',
      'task_failed', 'task_completed',
      'system_alert', 'notification_created',
    ]
    const unsubs = events.map(type =>
      useRealtimeStore.getState().subscribe(type, () => debouncedRefresh())
    )
    return () => unsubs.forEach(u => u())
  }, [debouncedRefresh])

  const loadInbox = async () => {
    try {
      setLoading(true)
      const [inboxRes, countsRes] = await Promise.all([
        officeService.getCEOInbox({
          filter_type: filterType || undefined,
          filter_priority: filterPriority || undefined,
          unread_only: unreadOnly || undefined,
        }),
        officeService.getCEOInboxCounts(),
      ])
      setItems(inboxRes.data ?? [])
      setCounts(countsRes.data ?? null)
    } catch (err) {
      console.error('Failed to load inbox:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (item: CEOInboxItem) => {
    try {
      await officeService.approveInboxItem(item.type, item.id)
      await loadInbox()
    } catch (err) {
      console.error('Failed to approve:', err)
    }
  }

  const handleReject = async (item: CEOInboxItem) => {
    try {
      await officeService.rejectInboxItem(item.type, item.id)
      await loadInbox()
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

  const handleArchive = async (item: CEOInboxItem) => {
    try {
      await officeService.archiveInboxItem(item.type, item.id)
      await loadInbox()
    } catch (err) {
      console.error('Failed to archive:', err)
    }
  }

  const handleResolve = async (item: CEOInboxItem) => {
    try {
      await officeService.resolveInboxItem(item.type, item.id)
      await loadInbox()
    } catch (err) {
      console.error('Failed to resolve:', err)
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

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Attention Center</h1>
            <p className="text-white/50 mt-1">Important events requiring your action</p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleMarkAllRead}
              className="px-4 py-2 text-sm font-medium text-white/80 bg-white/5 border border-white/15 rounded-lg hover:bg-white/10 transition-colors">
              Mark All Read
            </button>
            <button onClick={loadInbox}
              className="px-4 py-2 text-sm font-medium text-white/80 bg-white/5 border border-white/15 rounded-lg hover:bg-white/10 transition-colors">
              â†» Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Count Cards */}
      {counts && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <button onClick={() => setFilterType(null)}
            className={`p-3 rounded-xl border text-left transition-colors ${
              !filterType ? 'bg-indigo-500/10 border-indigo-500/30' : 'bg-white border-white/10 hover:border-white/20'
            }`}>
            <div className="text-xl font-bold text-white">{counts.total}</div>
            <div className="text-xs text-white/50">Total</div>
          </button>
          <button onClick={() => setFilterType(filterType === 'approval' ? null : 'approval')}
            className={`p-3 rounded-xl border text-left transition-colors ${
              filterType === 'approval' ? 'bg-amber-500/10 border-amber-500/25' : 'bg-white border-white/10 hover:border-white/20'
            }`}>
            <div className="text-xl font-bold text-amber-600">{counts.pending_approvals}</div>
            <div className="text-xs text-white/50">Approvals</div>
          </button>
          <button onClick={() => setFilterType(filterType === 'agent_error' ? null : 'agent_error')}
            className={`p-3 rounded-xl border text-left transition-colors ${
              filterType === 'agent_error' ? 'bg-red-500/10 border-red-500/25' : 'bg-white border-white/10 hover:border-white/20'
            }`}>
            <div className="text-xl font-bold text-red-600">{counts.error_agents}</div>
            <div className="text-xs text-white/50">Agent Errors</div>
          </button>
          <button onClick={() => setFilterType(filterType === 'failed_task' ? null : 'failed_task')}
            className={`p-3 rounded-xl border text-left transition-colors ${
              filterType === 'failed_task' ? 'bg-red-500/10 border-red-500/25' : 'bg-white border-white/10 hover:border-white/20'
            }`}>
            <div className="text-xl font-bold text-red-600">{counts.failed_tasks}</div>
            <div className="text-xs text-white/50">Failed Tasks</div>
          </button>
          <button onClick={() => setFilterType(filterType === 'system_alert' ? null : 'system_alert')}
            className={`p-3 rounded-xl border text-left transition-colors ${
              filterType === 'system_alert' ? 'bg-orange-500/10 border-orange-500/25' : 'bg-white border-white/10 hover:border-white/20'
            }`}>
            <div className="text-xl font-bold text-orange-600">{counts.system_alerts}</div>
            <div className="text-xs text-white/50">System Alerts</div>
          </button>
          <button onClick={() => setUnreadOnly(!unreadOnly)}
            className={`p-3 rounded-xl border text-left transition-colors ${
              unreadOnly ? 'bg-blue-500/10 border-blue-500/25' : 'bg-white border-white/10 hover:border-white/20'
            }`}>
            <div className="text-xl font-bold text-blue-600">{counts.unread_notifications}</div>
            <div className="text-xs text-white/50">Unread</div>
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex items-center gap-2">
          <span className="text-sm text-white/50">Priority:</span>
          {['critical', 'high', 'medium', 'low'].map((p) => {
            const config = PRIORITY_CONFIG[p]
            return (
              <button key={p} onClick={() => setFilterPriority(filterPriority === p ? null : p)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                  filterPriority === p ? `${config.color}` : 'bg-white/10 text-white/70 hover:bg-white/15'
                }`}>
                {config.label}
              </button>
            )
          })}
        </div>
        {filterType && (
          <button onClick={() => setFilterType(null)}
            className="px-3 py-1.5 text-xs font-medium text-indigo-400 bg-indigo-500/10 rounded-lg hover:bg-indigo-500/20">
            Clear Type Filter
          </button>
        )}
        {filterPriority && (
          <button onClick={() => setFilterPriority(null)}
            className="px-3 py-1.5 text-xs font-medium text-indigo-400 bg-indigo-500/10 rounded-lg hover:bg-indigo-500/20">
            Clear Priority Filter
          </button>
        )}
      </div>

      {/* Items */}
      {loading ? (
        <div className="flex items-center justify-center min-h-[200px]">
          <div className="text-center">
            <div className="w-8 h-8 border-4 border-white/10 border-t-indigo-400 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-white/50">Loading inbox...</p>
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-4">âœ…</div>
          <p className="text-lg font-medium text-white">All clear!</p>
          <p className="text-sm text-white/50 mt-1">No items require your attention right now.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {items.map((item, i) => (
            <InboxItemCard
              key={`${item.type}-${item.id}-${i}`}
              item={item}
              onApprove={handleApprove}
              onReject={handleReject}
              onDismiss={handleDismiss}
              onArchive={handleArchive}
              onResolve={handleResolve}
            />
          ))}
        </div>
      )}
    </div>
  )
}
