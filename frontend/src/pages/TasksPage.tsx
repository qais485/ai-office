import { useState, useEffect } from 'react'
import type { Task, TaskStats } from '../types'
import { officeService } from '../services/office'

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  pending: { label: 'Pending', color: 'bg-blue-100 text-blue-700', icon: '○' },
  running: { label: 'Running', color: 'bg-amber-100 text-amber-700', icon: '⟳' },
  waiting_approval: { label: 'Waiting Approval', color: 'bg-purple-100 text-purple-700', icon: '⏳' },
  completed: { label: 'Completed', color: 'bg-green-100 text-green-700', icon: '✓' },
  failed: { label: 'Failed', color: 'bg-red-100 text-red-700', icon: '✗' },
  cancelled: { label: 'Cancelled', color: 'bg-gray-100 text-gray-600', icon: '⊘' },
}

const TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  tool_execution: { label: 'Tool', color: 'bg-cyan-100 text-cyan-700' },
  agent_collaboration: { label: 'Collaboration', color: 'bg-indigo-100 text-indigo-700' },
  approval_required: { label: 'Approval', color: 'bg-amber-100 text-amber-700' },
  general: { label: 'General', color: 'bg-gray-100 text-gray-600' },
}

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: 'Low', color: 'bg-gray-100 text-gray-600' },
  medium: { label: 'Medium', color: 'bg-blue-100 text-blue-700' },
  high: { label: 'High', color: 'bg-orange-100 text-orange-700' },
  urgent: { label: 'Urgent', color: 'bg-red-100 text-red-700' },
}

function TaskCard({ task, onCancel }: { task: Task; onCancel: (id: string) => void }) {
  const status = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending
  const taskType = TYPE_CONFIG[task.task_type] || TYPE_CONFIG.general
  const priority = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium
  const isRunning = task.status === 'running' || task.status === 'pending'

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg ${status.color}`}>
            {status.icon}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{task.title}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${status.color}`}>
                {status.label}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${taskType.color}`}>
                {taskType.label}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${priority.color}`}>
                {priority.label}
              </span>
            </div>
          </div>
        </div>
      </div>

      {task.description && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{task.description}</p>
      )}

      <div className="space-y-1.5 mb-4">
        <div className="flex items-center text-sm">
          <span className="text-gray-500 w-20">Agent:</span>
          <span className="font-medium text-gray-900">{task.agent_name || 'Unknown'}</span>
        </div>
        {task.tool_name && (
          <div className="flex items-center text-sm">
            <span className="text-gray-500 w-20">Tool:</span>
            <span className="text-gray-700">{task.tool_name}{task.tool_action ? ` / ${task.tool_action}` : ''}</span>
          </div>
        )}
        {task.started_at && (
          <div className="flex items-center text-sm">
            <span className="text-gray-500 w-20">Started:</span>
            <span className="text-gray-700">{new Date(task.started_at).toLocaleString()}</span>
          </div>
        )}
        {task.completed_at && (
          <div className="flex items-center text-sm">
            <span className="text-gray-500 w-20">Finished:</span>
            <span className="text-gray-700">{new Date(task.completed_at).toLocaleString()}</span>
          </div>
        )}
      </div>

      {task.error_message && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
          <p className="text-sm text-red-700">{task.error_message}</p>
        </div>
      )}

      {task.result && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
          <p className="text-sm text-green-700 line-clamp-3">{task.result}</p>
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">
          {new Date(task.created_at).toLocaleString()}
        </span>
        <div className="flex items-center gap-2">
          {isRunning && (
            <button
              onClick={() => onCancel(task.id)}
              className="px-3 py-1.5 bg-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-300 transition-colors"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string | null>(null)
  const [filterPriority, setFilterPriority] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [filterStatus, filterType, filterPriority])

  const loadData = async () => {
    try {
      setLoading(true)
      const [tasksRes, statsRes] = await Promise.all([
        officeService.getTasks({
          status: filterStatus || undefined,
          task_type: filterType || undefined,
          priority: filterPriority || undefined,
        }),
        officeService.getTaskStats(),
      ])
      setTasks(tasksRes.data)
      setStats(statsRes.data)
    } catch (err) {
      setError('Failed to load tasks')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async (id: string) => {
    try {
      await officeService.cancelTask(id)
      await loadData()
    } catch (err) {
      console.error('Failed to cancel task:', err)
    }
  }

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading tasks...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-600 mb-2">{error}</p>
          <button onClick={loadData} className="text-sm text-primary-600 hover:text-primary-700">
            Try again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Task Center</h1>
        <p className="text-gray-500 mt-1">Track and manage all agent tasks</p>
      </div>

      {stats && (
        <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-7 gap-3 mb-8">
          <button
            onClick={() => setFilterStatus(null)}
            className={`p-3 rounded-xl border transition-colors text-left ${
              !filterStatus
                ? 'bg-primary-50 border-primary-200'
                : 'bg-white border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="text-xl font-bold text-gray-900">{stats.total}</div>
            <div className="text-xs text-gray-500">Total</div>
          </button>
          {[
            { key: 'pending', label: 'Pending', color: 'text-blue-600', count: stats.pending },
            { key: 'running', label: 'Running', color: 'text-amber-600', count: stats.running },
            { key: 'waiting_approval', label: 'Approval', color: 'text-purple-600', count: stats.waiting_approval },
            { key: 'completed', label: 'Done', color: 'text-green-600', count: stats.completed },
            { key: 'failed', label: 'Failed', color: 'text-red-600', count: stats.failed },
            { key: 'cancelled', label: 'Cancelled', color: 'text-gray-600', count: stats.cancelled },
          ].map((item) => (
            <button
              key={item.key}
              onClick={() => setFilterStatus(filterStatus === item.key ? null : item.key)}
              className={`p-3 rounded-xl border transition-colors text-left ${
                filterStatus === item.key
                  ? 'bg-primary-50 border-primary-200'
                  : 'bg-white border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className={`text-xl font-bold ${item.color}`}>{item.count}</div>
              <div className="text-xs text-gray-500">{item.label}</div>
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Type:</span>
          {Object.entries(TYPE_CONFIG).map(([key, config]) => (
            <button
              key={key}
              onClick={() => setFilterType(filterType === key ? null : key)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                filterType === key
                  ? `${config.color}`
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {config.label}
            </button>
          ))}
        </div>
        <div className="h-4 w-px bg-gray-200" />
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Priority:</span>
          {Object.entries(PRIORITY_CONFIG).map(([key, config]) => (
            <button
              key={key}
              onClick={() => setFilterPriority(filterPriority === key ? null : key)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                filterPriority === key
                  ? `${config.color}`
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {config.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onCancel={handleCancel} />
        ))}
      </div>

      {tasks.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No tasks found</p>
        </div>
      )}
    </div>
  )
}
