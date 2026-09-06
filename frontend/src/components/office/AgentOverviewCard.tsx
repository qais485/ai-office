import type { AIAgent, AgentActivity, OfficeRoom, Task } from '../../types'
import { formatTimeAgo, parseServerDate, shortActivityLabel } from '../../lib/utils'

const AGENT_STATUS_DOT: Record<string, string> = {
  active: 'bg-green-500',
  paused: 'bg-amber-500',
  inactive: 'bg-gray-400',
  error: 'bg-red-500',
  disabled: 'bg-red-400',
  draft: 'bg-gray-300',
  archived: 'bg-gray-300',
}

const AGENT_STATUS_BADGE: Record<string, string> = {
  active: 'bg-green-500/15 text-green-400 border border-green-500/20',
  paused: 'bg-amber-500/15 text-amber-400 border border-amber-500/20',
  inactive: 'bg-white/5 text-white/40 border border-white/10',
  error: 'bg-red-500/15 text-red-400 border border-red-500/20',
  disabled: 'bg-red-500/10 text-red-400/60 border border-red-500/10',
  draft: 'bg-white/5 text-white/30 border border-white/8',
  archived: 'bg-white/5 text-white/20 border border-white/8',
}

const AGENT_AVATAR_COLORS: Record<string, { bg: string; text: string }> = {
  active: { bg: 'bg-green-500/15', text: 'text-green-400' },
  paused: { bg: 'bg-amber-500/15', text: 'text-amber-400' },
  inactive: { bg: 'bg-white/5', text: 'text-white/40' },
  error: { bg: 'bg-red-500/15', text: 'text-red-400' },
  disabled: { bg: 'bg-red-500/10', text: 'text-red-400/60' },
  draft: { bg: 'bg-white/5', text: 'text-white/30' },
  archived: { bg: 'bg-white/5', text: 'text-white/20' },
}

interface AgentOverviewCardProps {
  agent: AIAgent
  room: OfficeRoom
  activities: AgentActivity[]
  currentTask?: Task | null
}

/** Activities newer than this are still considered "current". */
const CURRENT_ACTIVITY_WINDOW_MS = 10 * 60 * 1000

/** Exactly four states for the Current Activity card. */
const CURRENT_ACTIVITY_VIEW: Record<string, { label: string; box: string; dot: string; sub: string; text: string }> = {
  working: { label: 'Working on a task', box: 'bg-amber-500/10 border-amber-500/20', dot: 'bg-amber-400 animate-pulse', sub: 'text-amber-400/60', text: 'text-amber-400' },
  waiting: { label: 'Waiting for approval', box: 'bg-amber-500/10 border-amber-500/20', dot: 'bg-amber-400 animate-pulse', sub: 'text-amber-400/60', text: 'text-amber-400' },
  completed: { label: 'Completed a task', box: 'bg-green-500/10 border-green-500/20', dot: 'bg-green-400', sub: 'text-green-400/60', text: 'text-green-400' },
  failed: { label: 'Task failed', box: 'bg-red-500/10 border-red-500/20', dot: 'bg-red-400', sub: 'text-red-400/60', text: 'text-red-400' },
  idle: { label: 'Idle', box: 'bg-white/3 border-white/6', dot: 'bg-gray-500', sub: 'text-white/30', text: 'text-white/40' },
}

export default function AgentOverviewCard({ agent, room, activities, currentTask = null }: AgentOverviewCardProps) {
  const latestActivity = activities
    .filter(a => a.agent_id === agent.id)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] ?? null

  const latestAge = latestActivity ? Date.now() - (parseServerDate(latestActivity.created_at)?.getTime() ?? 0) : Infinity
  const finishedRecently: 'completed' | 'failed' | null =
    latestActivity && latestAge < CURRENT_ACTIVITY_WINDOW_MS
      ? latestActivity.activity_type === 'task_failed' || latestActivity.status === 'failed'
        ? 'failed'
        : latestActivity.activity_type === 'task_completed'
          ? 'completed'
          : null
      : null

  const activityState: string =
    currentTask?.status === 'running' ? 'working'
    : currentTask?.status === 'waiting_approval' ? 'waiting'
    : finishedRecently ?? 'idle'
  const activityView = CURRENT_ACTIVITY_VIEW[activityState]

  const avatarStyle = AGENT_AVATAR_COLORS[agent.lifecycle_status] ?? AGENT_AVATAR_COLORS.inactive

  return (
    <div className="rounded-xl bg-white/3 border border-white/6 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border-b border-white/6">
        <div className="flex items-center gap-4">
          <div className={`flex items-center justify-center h-14 w-14 rounded-xl ${avatarStyle.bg} ${avatarStyle.text} text-xl font-bold shrink-0 border border-white/10`}>
            {agent.name.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-white truncate">{agent.name}</h3>
              <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${AGENT_STATUS_DOT[agent.lifecycle_status] ?? 'bg-gray-400'}`} />
            </div>
            <p className="text-sm text-white/40 mt-0.5">{agent.role}</p>
          </div>
          <span className={`text-xs font-semibold px-3 py-1 rounded-full ${AGENT_STATUS_BADGE[agent.lifecycle_status] ?? AGENT_STATUS_BADGE.inactive}`}>
            {agent.lifecycle_status}
          </span>
        </div>
      </div>

      {/* Details */}
      <div className="px-5 py-4 space-y-3">
        {agent.description && (
          <p className="text-sm text-white/50 line-clamp-2">{agent.description}</p>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div className="flex items-center gap-2 p-2.5 bg-white/3 rounded-lg border border-white/6">
            <div className="min-w-0">
              <p className="text-[10px] text-white/30 uppercase tracking-wider">Room</p>
              <p className="text-sm font-medium text-white truncate">{room.name}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 p-2.5 bg-white/3 rounded-lg border border-white/6">
            <div className="min-w-0">
              <p className="text-[10px] text-white/30 uppercase tracking-wider">Last Active</p>
              {latestActivity ? (
                <p
                  className="text-sm font-medium text-white truncate"
                  title={`${latestActivity.description ?? latestActivity.activity_type} · ${parseServerDate(latestActivity.created_at)?.toLocaleString() ?? ''}`}
                >
                  {formatTimeAgo(latestActivity.created_at)}
                  <span className="text-white/40 font-normal"> · {shortActivityLabel(latestActivity)}</span>
                </p>
              ) : agent.last_active_at ? (
                <p className="text-sm font-medium text-white">{formatTimeAgo(agent.last_active_at)}</p>
              ) : (
                <p className="text-sm font-medium text-white/40">Never</p>
              )}
            </div>
          </div>

          {agent.hired_at && (
            <div className="flex items-center gap-2 p-2.5 bg-white/3 rounded-lg border border-white/6">
              <div className="min-w-0">
                <p className="text-[10px] text-white/30 uppercase tracking-wider">Hired</p>
                <p className="text-sm font-medium text-white">{parseServerDate(agent.hired_at)?.toLocaleDateString() ?? '—'}</p>
              </div>
            </div>
          )}

          <div className={`flex items-center gap-2 p-2.5 rounded-lg border ${activityView.box}`}>
            <span className={`h-2 w-2 rounded-full shrink-0 ${activityView.dot}`} />
            <div className="min-w-0">
              <p className={`text-[10px] uppercase tracking-wider ${activityView.sub}`}>
                Current Activity
              </p>
              <p
                className={`text-sm font-medium truncate ${activityView.text}`}
                title={activityView.label}
              >
                {activityView.label}
              </p>
            </div>
          </div>
        </div>

        {agent.last_error && (
          <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
            <p className="text-xs font-semibold text-red-400">Last Error</p>
            <p className="text-xs text-red-400/70 mt-0.5">{agent.last_error}</p>
          </div>
        )}
      </div>
    </div>
  )
}
