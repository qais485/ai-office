import { useMemo, useState } from 'react'
import type { OfficeRoom, AIAgent, Task, AgentActivity } from '../../types'
import { X, ArrowRight, CheckCircle, Clock, AlertCircle, Trash2, UserPlus, Loader2 } from 'lucide-react'
import { getLatestActivity } from '../../lib/utils'

const AGENT_STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-500/15 text-green-400 border-green-500/20',
  paused: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  inactive: 'bg-white/5 text-white/40 border-white/10',
  error: 'bg-red-500/15 text-red-400 border-red-500/20',
  disabled: 'bg-red-500/10 text-red-400/60 border-red-500/10',
  draft: 'bg-white/5 text-white/30 border-white/8',
  archived: 'bg-white/5 text-white/20 border-white/8',
}

const TASK_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-blue-500/15 text-blue-400',
  running: 'bg-amber-500/15 text-amber-400',
  waiting_approval: 'bg-purple-500/15 text-purple-400',
  completed: 'bg-green-500/15 text-green-400',
  failed: 'bg-red-500/15 text-red-400',
  cancelled: 'bg-white/5 text-white/40',
}

interface RoomDetailProps {
  room: OfficeRoom
  agents: AIAgent[]
  tasks: Task[]
  activities: AgentActivity[]
  onClose: () => void
  onEnter: (room: OfficeRoom) => void
  onDelete?: (roomId: string) => Promise<{ success: boolean; error?: string }>
  onAssignAgent?: (agentId: string, roomId: string | null) => Promise<{ success: boolean; error?: string }>
}

export default function RoomDetail({ room, agents, tasks, activities, onClose, onEnter, onDelete, onAssignAgent }: RoomDetailProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [isAssigning, setIsAssigning] = useState(false)

  const roomAgents = agents.filter((a) => a.room_id === room.id)
  const availableAgents = agents.filter((a) => a.room_id !== room.id && a.lifecycle_status !== 'archived')
  const agentIds = new Set(roomAgents.map((a) => a.id))
  const roomTasks = tasks.filter((t) => agentIds.has(t.agent_id))

  const pendingTasks = roomTasks.filter((t) => t.status === 'pending').length
  const activeTasks = roomTasks.filter((t) => t.status === 'running').length
  const completedTasks = roomTasks.filter((t) => t.status === 'completed').length

  const agentLatestActivities = useMemo(() => {
    const map = new Map<string, AgentActivity | null>()
    for (const agent of roomAgents) {
      map.set(agent.id, getLatestActivity(activities, agent.id))
    }
    return map
  }, [activities, roomAgents])

  return (
    <div className="w-full flex flex-col bg-[#0a0a14] rounded-2xl border border-white/8 shadow-2xl overflow-hidden max-h-[80vh]">
      {/* Header */}
      <div className="px-4 py-4 border-b border-white/6 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-white truncate">{room.name}</h2>
          {room.description && (
            <p className="text-[11px] text-white/40 mt-0.5 line-clamp-2">{room.description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 p-1 rounded-md text-white/40 hover:text-white hover:bg-white/8 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Action Buttons */}
        <div className="px-4 py-3 border-b border-white/6 space-y-2">
          <button
            type="button"
            onClick={() => onEnter(room)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 transition-colors"
          >
            Enter Room
            <ArrowRight size={14} />
          </button>

          {onDelete && (
            <>
              {showConfirm ? (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowConfirm(false)}
                    className="flex-1 px-3 py-1.5 text-xs font-medium text-white/60 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      setIsDeleting(true)
                      try {
                        await onDelete(room.id)
                      } finally {
                        setIsDeleting(false)
                        setShowConfirm(false)
                      }
                    }}
                    disabled={isDeleting}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg hover:bg-red-500/20 disabled:opacity-50 transition-colors"
                  >
                    {isDeleting ? (
                      <div className="animate-spin h-3 w-3 border-2 border-red-300 border-t-red-500 rounded-full" />
                    ) : (
                      <Trash2 size={12} />
                    )}
                    Delete
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowConfirm(true)}
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-400/60 bg-white/3 border border-white/6 rounded-lg hover:text-red-400 hover:bg-red-500/10 hover:border-red-500/20 transition-colors"
                >
                  <Trash2 size={12} />
                  Delete Room
                </button>
              )}
            </>
          )}
        </div>

        {/* Agents */}
        <div className="px-4 py-3 border-b border-white/6">
          <h3 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-2">Agents</h3>
          {roomAgents.length === 0 ? (
            <p className="text-xs text-white/20">No agents assigned</p>
          ) : (
            <ul className="space-y-2">
              {roomAgents.map((agent) => {
                const latestActivity = agentLatestActivities.get(agent.id)
                return (
                  <li key={agent.id} className="flex items-start gap-2.5 group">
                    <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-indigo-500/15 border border-indigo-500/20 text-indigo-400 text-xs font-medium shrink-0 mt-0.5">
                      {agent.name.charAt(0)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white truncate">{agent.name}</span>
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full border ${AGENT_STATUS_COLORS[agent.lifecycle_status] ?? AGENT_STATUS_COLORS.inactive}`}>
                          {agent.lifecycle_status}
                        </span>
                      </div>
                      <p className="text-[11px] text-white/30 truncate">{agent.role}</p>
                      {latestActivity?.description && (
                        <p className="text-[10px] text-amber-400/60 truncate mt-0.5">{latestActivity.description}</p>
                      )}
                    </div>
                    {onAssignAgent && (
                      <button
                        type="button"
                        onClick={async () => {
                          await onAssignAgent(agent.id, null)
                        }}
                        className="shrink-0 mt-0.5 p-1 text-white/20 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors opacity-0 group-hover:opacity-100"
                        title="Remove from room"
                      >
                        <X size={12} />
                      </button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Assign Agent */}
        {onAssignAgent && availableAgents.length > 0 && (
          <div className="px-4 py-3 border-b border-white/6">
            <h3 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-2">Assign Agent</h3>
            <div className="flex gap-2">
              <select
                value={selectedAgentId}
                onChange={(e) => setSelectedAgentId(e.target.value)}
                className="flex-1 px-2 py-1.5 text-xs bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-white/20"
              >
                <option value="">Select agent...</option>
                {availableAgents.map((agent) => (
                  <option key={agent.id} value={agent.id}>{agent.name} ({agent.role})</option>
                ))}
              </select>
              <button
                type="button"
                onClick={async () => {
                  if (!selectedAgentId || !onAssignAgent) return
                  setIsAssigning(true)
                  try {
                    await onAssignAgent(selectedAgentId, room.id)
                    setSelectedAgentId('')
                  } finally {
                    setIsAssigning(false)
                  }
                }}
                disabled={!selectedAgentId || isAssigning}
                className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 rounded-lg hover:bg-indigo-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {isAssigning ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <UserPlus size={12} />
                )}
                Add
              </button>
            </div>
          </div>
        )}

        {/* Task Summary */}
        <div className="px-4 py-3 border-b border-white/6">
          <h3 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-2">Task Summary</h3>
          <div className="grid grid-cols-3 gap-2">
            <div className="text-center p-2.5 rounded-lg bg-white/3 border border-white/6">
              <Clock size={14} className="mx-auto text-blue-400 mb-1" />
              <p className="text-lg font-semibold text-white">{pendingTasks}</p>
              <p className="text-[10px] text-white/30">Pending</p>
            </div>
            <div className="text-center p-2.5 rounded-lg bg-white/3 border border-white/6">
              <AlertCircle size={14} className="mx-auto text-amber-400 mb-1" />
              <p className="text-lg font-semibold text-white">{activeTasks}</p>
              <p className="text-[10px] text-white/30">Active</p>
            </div>
            <div className="text-center p-2.5 rounded-lg bg-white/3 border border-white/6">
              <CheckCircle size={14} className="mx-auto text-green-400 mb-1" />
              <p className="text-lg font-semibold text-white">{completedTasks}</p>
              <p className="text-[10px] text-white/30">Done</p>
            </div>
          </div>
        </div>

        {/* Recent Tasks */}
        {roomTasks.length > 0 && (
          <div className="px-4 py-3">
            <h3 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-2">Tasks</h3>
            <ul className="space-y-1.5">
              {roomTasks.slice(0, 5).map((task) => (
                <li key={task.id} className="flex items-center justify-between gap-2 py-1.5 px-2 rounded-md hover:bg-white/3 transition-colors">
                  <span className="text-xs text-white/60 truncate">{task.title}</span>
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full shrink-0 ${TASK_STATUS_COLORS[task.status] ?? 'bg-white/5 text-white/40'}`}>
                    {task.status.replace('_', ' ')}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
