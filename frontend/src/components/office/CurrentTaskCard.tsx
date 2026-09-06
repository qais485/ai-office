import type { Task } from '../../types'
import { formatTimeAgo, parseServerDate } from '../../lib/utils'

const TASK_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-blue-500/15 text-blue-400',
  running: 'bg-amber-500/15 text-amber-400',
  waiting_approval: 'bg-purple-500/15 text-purple-400',
  completed: 'bg-green-500/15 text-green-400',
  failed: 'bg-red-500/15 text-red-400',
  cancelled: 'bg-white/5 text-white/40',
}

interface CurrentTaskCardProps {
  task: Task | null
}

export default function CurrentTaskCard({ task }: CurrentTaskCardProps) {
  if (!task) {
    return (
      <div className="rounded-xl bg-white/3 border border-white/6 p-5">
        <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider mb-3">Current Task</h3>
        <div className="text-center py-6">
          <div className="inline-flex items-center justify-center h-10 w-10 rounded-xl bg-white/5 border border-white/10 mb-2">
            <svg className="h-5 w-5 text-white/20" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m6 4.125l2.25 2.25m0 0l2.25 2.25M12 13.875l2.25-2.25M12 13.875l-2.25 2.25M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
            </svg>
          </div>
          <p className="text-sm text-white/30">No active task</p>
          <p className="text-xs text-white/20 mt-0.5">Agent is idle</p>
        </div>
      </div>
    )
  }

  const statusColor = TASK_STATUS_COLORS[task.status] ?? 'bg-white/5 text-white/40'
  const isRunning = task.status === 'running'
  const startedAt = parseServerDate(task.started_at)
  const elapsed = startedAt ? Math.floor((Date.now() - startedAt.getTime()) / 60000) : 0

  return (
    <div className="rounded-xl bg-white/3 border border-white/6 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider">Current Task</h3>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${statusColor}`}>
          {task.status.replace('_', ' ')}
        </span>
      </div>

      <div className="space-y-3">
        <div>
          <p className="text-sm font-semibold text-white">{task.title}</p>
          {task.description && (
            <p className="text-xs text-white/40 mt-1 line-clamp-2">{task.description}</p>
          )}
        </div>

        {isRunning && (
          <div>
            <div className="flex items-center justify-between text-[10px] text-white/30 mb-1">
              <span>Progress</span>
              <span>{elapsed}m elapsed</span>
            </div>
            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full bg-amber-400 rounded-full animate-pulse" style={{ width: '60%' }} />
            </div>
          </div>
        )}

        <div className="flex items-center gap-4 text-[10px] text-white/30">
          {task.tool_name && (
            <span className="bg-white/5 px-1.5 py-0.5 rounded">{task.tool_name}</span>
          )}
          {task.started_at && (
            <span>Started {formatTimeAgo(task.started_at)}</span>
          )}
          <div className="flex items-center gap-1">
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${task.priority === 'urgent' ? 'bg-red-500' : task.priority === 'high' ? 'bg-amber-500' : task.priority === 'medium' ? 'bg-blue-500' : 'bg-gray-400'}`} />
            <span>{task.priority}</span>
          </div>
        </div>

        {task.error_message && (
          <div className="p-2 bg-red-500/10 rounded-lg border border-red-500/20">
            <p className="text-xs text-red-400">{task.error_message}</p>
          </div>
        )}
      </div>
    </div>
  )
}
