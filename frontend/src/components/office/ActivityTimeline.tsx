import type { AgentActivity } from '../../types'
import { formatTimeAgo } from '../../lib/utils'

const ACTIVITY_TYPE_ICONS: Record<string, string> = {
  task_created: 'M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  task_completed: 'M9 12.75L11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  task_failed: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126Z',
  tool_used: 'M11.42 15.17l-5.384 3.18A1.125 1.125 0 014.5 17.31V6.69a1.125 1.125 0 011.536-1.04l5.384 3.18a1.125 1.125 0 010 1.94z',
  approval_requested: 'M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z',
  agent_lifecycle: 'M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182',
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-green-400',
  failed: 'text-red-400',
  running: 'text-amber-400',
  pending: 'text-blue-400',
  error: 'text-red-400',
  success: 'text-green-400',
}

interface ActivityTimelineProps {
  activities: AgentActivity[]
}

export default function ActivityTimeline({ activities }: ActivityTimelineProps) {
  if (activities.length === 0) {
    return (
      <div className="rounded-xl bg-white/3 border border-white/6 p-5">
        <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider mb-4">Recent Activity</h3>
        <div className="text-center py-8">
          <div className="inline-flex items-center justify-center h-10 w-10 rounded-xl bg-white/5 border border-white/10 mb-2">
            <svg className="h-5 w-5 text-white/20" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <p className="text-sm text-white/30">No activity yet</p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl bg-white/3 border border-white/6 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider">Recent Activity</h3>
        <span className="text-[10px] text-white/20">{activities.length} events</span>
      </div>

      <div className="space-y-1">
        {activities.slice(0, 10).map((activity) => {
          const iconPath = ACTIVITY_TYPE_ICONS[activity.activity_type] ?? ACTIVITY_TYPE_ICONS.tool_used
          const statusColor = STATUS_COLORS[activity.status ?? ''] ?? 'text-white/30'
          const isError = activity.activity_type === 'task_failed' || activity.status === 'error' || activity.status === 'failed'

          return (
            <div key={activity.id} className="flex items-start gap-3 py-2.5 px-2 rounded-lg hover:bg-white/3 transition-colors">
              <div className={`flex items-center justify-center h-7 w-7 rounded-lg shrink-0 mt-0.5 ${isError ? 'bg-red-500/10' : 'bg-white/5'}`}>
                <svg className={`h-3.5 w-3.5 ${isError ? 'text-red-400' : 'text-white/40'}`} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d={iconPath} />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white/60 leading-snug">{activity.description ?? activity.activity_type}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] text-white/20">{formatTimeAgo(activity.created_at)}</span>
                  {activity.tool_name && (
                    <span className="text-[10px] text-white/20 bg-white/5 px-1.5 py-0.5 rounded">{activity.tool_name}</span>
                  )}
                </div>
              </div>
              {activity.status && (
                <span className={`text-[10px] font-medium capitalize shrink-0 ${statusColor}`}>
                  {activity.status}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
