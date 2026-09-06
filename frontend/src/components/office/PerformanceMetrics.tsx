import type { Task } from '../../types'
import { parseServerDate } from '../../lib/utils'

interface PerformanceMetricsProps {
  tasks: Task[]
}

export default function PerformanceMetrics({ tasks }: PerformanceMetricsProps) {
  const total = tasks.length
  const completed = tasks.filter(t => t.status === 'completed').length
  const failed = tasks.filter(t => t.status === 'failed').length
  const running = tasks.filter(t => t.status === 'running').length
  const pending = tasks.filter(t => t.status === 'pending').length
  const waitingApproval = tasks.filter(t => t.status === 'waiting_approval').length
  const successRate = total > 0 && (completed + failed) > 0 ? Math.round((completed / (completed + failed)) * 100) : 0

  const avgCompletionTime = (() => {
    const completedTasks = tasks.filter(t => t.status === 'completed' && t.started_at && t.completed_at)
    if (completedTasks.length === 0) return null
    const totalMinutes = completedTasks.reduce((sum, t) => {
      const start = parseServerDate(t.started_at!)?.getTime() ?? NaN
      const end = parseServerDate(t.completed_at!)?.getTime() ?? NaN
      if (isNaN(start) || isNaN(end)) return sum
      return sum + (end - start) / 60000
    }, 0)
    return Math.round(totalMinutes / completedTasks.length)
  })()

  const metrics = [
    { label: 'Total', value: total, color: 'text-white' },
    { label: 'Completed', value: completed, color: 'text-green-400' },
    { label: 'Failed', value: failed, color: 'text-red-400' },
    { label: 'Running', value: running, color: 'text-amber-400' },
    { label: 'Pending', value: pending, color: 'text-blue-400' },
    { label: 'Waiting', value: waitingApproval, color: 'text-purple-400' },
  ]

  return (
    <div className="rounded-xl bg-white/3 border border-white/6 p-5">
      <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider mb-4">Performance</h3>

      {/* Success Rate */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-white/60">Success Rate</span>
          <span className={`text-lg font-bold ${successRate >= 80 ? 'text-green-400' : successRate >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
            {successRate}%
          </span>
        </div>
        <div className="h-2 bg-white/5 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${successRate >= 80 ? 'bg-green-500' : successRate >= 50 ? 'bg-amber-500' : 'bg-red-500'}`}
            style={{ width: `${successRate}%` }}
          />
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-3 gap-2">
        {metrics.map((metric) => (
          <div key={metric.label} className="text-center p-2.5 rounded-lg bg-white/3 border border-white/6">
            <p className={`text-xl font-bold ${metric.color}`}>{metric.value}</p>
            <p className="text-[10px] text-white/30 mt-0.5">{metric.label}</p>
          </div>
        ))}
      </div>

      {/* Avg Completion Time */}
      {avgCompletionTime !== null && (
        <div className="mt-4 p-3 bg-white/3 rounded-lg border border-white/6 flex items-center justify-between">
          <span className="text-xs text-white/30">Avg. Completion Time</span>
          <span className="text-sm font-semibold text-white">
            {avgCompletionTime < 1 ? '<1m' : `${avgCompletionTime}m`}
          </span>
        </div>
      )}

      {/* Task Type Breakdown */}
      {total > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-[10px] text-white/20 uppercase tracking-wider">Task Types</p>
          {['tool_execution', 'agent_collaboration', 'approval_required', 'general'].map((type) => {
            const count = tasks.filter(t => t.task_type === type).length
            if (count === 0) return null
            const pct = Math.round((count / total) * 100)
            const label = type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
            return (
              <div key={type} className="flex items-center gap-2">
                <span className="text-[10px] text-white/30 w-20 truncate">{label}</span>
                <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-[10px] text-white/20 w-8 text-right">{count}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
