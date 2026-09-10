import { useState, useMemo } from 'react'
import type { OfficeRoom, AIAgent, Task, AgentActivity, Approval } from '../../types'
import { parseServerDate } from '../../lib/utils'
import AgentOverviewCard from './AgentOverviewCard'
import CurrentTaskCard from './CurrentTaskCard'
import ActivityTimeline from './ActivityTimeline'
import ApprovalActions from './ApprovalActions'
import ApprovalDetailModal from './ApprovalDetailModal'
import PerformanceMetrics from './PerformanceMetrics'
import LifecycleControls from './LifecycleControls'
import AgentChatFAB from './AgentChatFAB'
import { LogOut, LayoutGrid, ClipboardList, Clock, Shield, BarChart3, Settings, Trash2 } from 'lucide-react'

const AGENT_STATUS_DOT: Record<string, string> = {
  active: 'bg-green-500',
  paused: 'bg-amber-500',
  inactive: 'bg-gray-400',
  error: 'bg-red-500',
  disabled: 'bg-red-400',
  draft: 'bg-gray-300',
  archived: 'bg-gray-300',
}

type DashboardTab = 'overview' | 'current_task' | 'activity' | 'approvals' | 'performance' | 'controls'

interface RoomDashboardProps {
  room: OfficeRoom
  agents: AIAgent[]
  tasks: Task[]
  activities: AgentActivity[]
  pendingApprovals: Approval[]
  onLeave: () => void
  onLifecycleAction: (agentId: string, action: 'pause' | 'resume' | 'disable' | 'archive' | 'restart', reason?: string) => Promise<{ success: boolean; error?: string }>
  onApproveApproval: (id: string) => Promise<{ success: boolean; error?: string }>
  onRejectApproval: (id: string) => Promise<{ success: boolean; error?: string }>
  onDelete?: (roomId: string) => Promise<{ success: boolean; error?: string }>
  onRefresh?: (silent?: boolean) => Promise<void>
}

const TAB_ICONS: Record<DashboardTab, typeof LayoutGrid> = {
  overview: LayoutGrid,
  current_task: ClipboardList,
  activity: Clock,
  approvals: Shield,
  performance: BarChart3,
  controls: Settings,
}

export default function RoomDashboard({ room, agents, tasks, activities, pendingApprovals, onLeave, onLifecycleAction, onApproveApproval, onRejectApproval, onDelete }: RoomDashboardProps) {
  const [activeTab, setActiveTab] = useState<DashboardTab>('overview')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const roomAgents = agents.filter((a) => a.room_id === room.id)
  const primaryAgent = roomAgents[0] ?? null
  const selectedAgent = selectedAgentId ? roomAgents.find(a => a.id === selectedAgentId) ?? primaryAgent : primaryAgent
  const agentIds = new Set(roomAgents.map((a) => a.id))
  const roomTasks = tasks.filter((t) => agentIds.has(t.agent_id))
  const roomActivities = activities.filter((a) => agentIds.has(a.agent_id))

  const currentTask = useMemo(() =>
    roomTasks.find(t => t.status === 'running' || t.status === 'waiting_approval') ?? null,
    [roomTasks]
  )

  const handleAction = async (action: 'pause' | 'resume' | 'disable' | 'archive' | 'restart') => {
    if (!selectedAgent) return { success: false as const }
    setActionLoading(`${selectedAgent.id}-${action}`)
    try {
      return await onLifecycleAction(selectedAgent.id, action)
    } finally {
      setActionLoading(null)
    }
  }

  const handleApprovalAction = async (id: string, type: 'approve' | 'reject') => {
    setActionLoading(`approval-${id}-${type}`)
    try {
      if (type === 'approve') return await onApproveApproval(id)
      return await onRejectApproval(id)
    } finally {
      setActionLoading(null)
    }
  }

  const tabs = useMemo(() => [
    { key: 'overview' as DashboardTab, label: 'Overview' },
    { key: 'current_task' as DashboardTab, label: 'Tasks' },
    { key: 'activity' as DashboardTab, label: 'Activity' },
    { key: 'approvals' as DashboardTab, label: 'Approvals', count: pendingApprovals.length || undefined },
    { key: 'performance' as DashboardTab, label: 'Performance' },
    { key: 'controls' as DashboardTab, label: 'Controls' },
  ], [pendingApprovals.length])

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-md" onClick={onLeave} />

      <div className="relative bg-[#0a0a14] rounded-2xl border border-white/8 shadow-2xl w-full max-w-3xl mx-4 max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/6 flex items-start justify-between gap-4 shrink-0">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold text-white truncate">{room.name}</h1>
              {primaryAgent && (
                <div className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${AGENT_STATUS_DOT[primaryAgent.lifecycle_status] ?? 'bg-gray-400'}`} />
                  <span className="text-xs text-white/40">{primaryAgent.name}</span>
                </div>
              )}
            </div>
            {room.description && (
              <p className="text-xs text-white/30 mt-0.5">{room.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {onDelete && (
              <>
                {showDeleteConfirm ? (
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setShowDeleteConfirm(false)}
                      className="px-2 py-1 text-[11px] font-medium text-white/40 bg-white/5 border border-white/10 rounded-md hover:bg-white/10 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        setIsDeleting(true)
                        try {
                          await onDelete(room.id)
                          onLeave()
                        } finally {
                          setIsDeleting(false)
                          setShowDeleteConfirm(false)
                        }
                      }}
                      disabled={isDeleting}
                      className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-red-400 bg-red-500/10 border border-red-500/20 rounded-md hover:bg-red-500/20 disabled:opacity-50 transition-colors"
                    >
                      {isDeleting ? (
                        <div className="animate-spin h-3 w-3 border-2 border-red-300 border-t-red-500 rounded-full" />
                      ) : (
                        <Trash2 size={11} />
                      )}
                      Confirm
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(true)}
                    className="p-1.5 text-white/30 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors"
                    title="Delete room"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </>
            )}
            <button
              type="button"
              onClick={onLeave}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white/60 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 hover:text-white transition-colors"
            >
              <LogOut size={14} />
              Leave
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="px-4 border-b border-white/6 flex gap-0.5 overflow-x-auto shrink-0">
          {tabs.map((tab) => {
            const Icon = TAB_ICONS[tab.key]
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === tab.key
                    ? 'border-indigo-500 text-indigo-400'
                    : 'border-transparent text-white/40 hover:text-white/60 hover:border-white/20'
                }`}
              >
                <Icon size={14} />
                {tab.label}
                {tab.count !== undefined && (
                  <span className="ml-0.5 px-1.5 py-0.5 text-[10px] font-medium bg-indigo-500/15 text-indigo-400 rounded-full">{tab.count}</span>
                )}
              </button>
            )
          })}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {/* Overview Tab */}
          {activeTab === 'overview' && primaryAgent && (
            <div className="space-y-5">
              <AgentOverviewCard agent={primaryAgent} room={room} activities={activities} currentTask={currentTask} />
              <CurrentTaskCard task={currentTask} />
              {roomActivities.length > 0 && (
                <ActivityTimeline activities={roomActivities.slice(0, 5)} />
              )}
            </div>
          )}

          {activeTab === 'overview' && !primaryAgent && (
            <div className="text-center py-12">
              <div className="inline-flex items-center justify-center h-12 w-12 rounded-xl bg-white/5 border border-white/10 mb-3">
                <svg className="h-6 w-6 text-white/20" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
                </svg>
              </div>
              <p className="text-sm text-white/30">No agents assigned to this room</p>
            </div>
          )}

          {/* Current Task Tab */}
          {activeTab === 'current_task' && (
            <div className="space-y-5">
              <CurrentTaskCard task={currentTask} />
              {roomTasks.length > 0 && (
                <div className="rounded-xl bg-white/3 border border-white/6 p-5">
                  <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider mb-3">All Tasks ({roomTasks.length})</h3>
                  <ul className="divide-y divide-white/6">
                    {roomTasks.slice(0, 8).map((task) => (
                      <li key={task.id} className="py-2.5 first:pt-0 last:pb-0">
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-white truncate">{task.title}</p>
                            <div className="flex items-center gap-2 mt-0.5">
                              {task.tool_name && (
                                <span className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded">{task.tool_name}</span>
                              )}
                              {task.started_at && (
                                <span className="text-[10px] text-white/20">{parseServerDate(task.started_at)?.toLocaleTimeString() ?? ''}</span>
                              )}
                            </div>
                          </div>
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0 ${
                            task.status === 'completed' ? 'bg-green-500/15 text-green-400' :
                            task.status === 'running' ? 'bg-amber-500/15 text-amber-400' :
                            task.status === 'failed' ? 'bg-red-500/15 text-red-400' :
                            task.status === 'waiting_approval' ? 'bg-purple-500/15 text-purple-400' :
                            'bg-white/5 text-white/40'
                          }`}>
                            {task.status.replace('_', ' ')}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Activity Tab */}
          {activeTab === 'activity' && (
            <ActivityTimeline activities={roomActivities} />
          )}

          {/* Approvals Tab */}
          {activeTab === 'approvals' && (
            <ApprovalActions
              approvals={pendingApprovals}
              onApprove={(id) => handleApprovalAction(id, 'approve')}
              onReject={(id) => handleApprovalAction(id, 'reject')}
              onSelect={setSelectedApproval}
            />
          )}

          {/* Performance Tab */}
          {activeTab === 'performance' && (
            <PerformanceMetrics tasks={roomTasks} />
          )}

          {/* Controls Tab */}
          {activeTab === 'controls' && roomAgents.length > 0 && (
            <div className="space-y-5">
              {roomAgents.length > 1 && (
                <div className="rounded-xl bg-white/3 border border-white/6 p-4">
                  <label className="block text-xs font-medium text-white/30 uppercase tracking-wider mb-2">Select Agent</label>
                  <select
                    value={selectedAgent?.id ?? ''}
                    onChange={(e) => setSelectedAgentId(e.target.value || null)}
                    className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-white/20"
                  >
                    {roomAgents.map((agent) => (
                      <option key={agent.id} value={agent.id}>{agent.name} ({agent.lifecycle_status})</option>
                    ))}
                  </select>
                </div>
              )}
              {selectedAgent && (
                <LifecycleControls
                  agent={selectedAgent}
                  onAction={handleAction}
                  actionLoading={actionLoading}
                />
              )}
            </div>
          )}

          {activeTab === 'controls' && roomAgents.length === 0 && (
            <div className="text-center py-12">
              <p className="text-sm text-white/30">No agents to control</p>
            </div>
          )}
        </div>
      </div>

      {selectedApproval && (
        <ApprovalDetailModal
          approvalId={selectedApproval.id}
          onClose={() => setSelectedApproval(null)}
          onApprove={(id) => handleApprovalAction(id, 'approve')}
          onReject={(id) => handleApprovalAction(id, 'reject')}
        />
      )}

      {/* Floating chat with the room's primary agent */}
      <AgentChatFAB agentId={primaryAgent?.id ?? null} agentName={primaryAgent?.name ?? 'Agent'} />
    </div>
  )
}
