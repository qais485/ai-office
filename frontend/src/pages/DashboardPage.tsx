import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import type { DashboardSummary, AgentSummary, TaskSummary } from '../types'
import { officeService } from '../services/office'
import { useAuthStore } from '../stores/useAuthStore'

const AGENT_STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  busy: 'bg-amber-100 text-amber-700',
  inactive: 'bg-gray-100 text-gray-500',
}

const TASK_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

const PRIORITY_COLORS: Record<string, string> = {
  high: 'text-red-600',
  medium: 'text-amber-600',
  low: 'text-gray-500',
}

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function StatCard({ label, value, detail, icon, color }: {
  label: string
  value: number
  detail: string
  icon: React.ReactNode
  color: 'primary' | 'emerald' | 'blue' | 'amber'
}) {
  const bgColors = {
    primary: 'bg-primary-50',
    emerald: 'bg-emerald-50',
    blue: 'bg-blue-50',
    amber: 'bg-amber-50',
  }
  const iconColors = {
    primary: 'text-primary-600',
    emerald: 'text-emerald-600',
    blue: 'text-blue-600',
    amber: 'text-amber-600',
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</h3>
        <span className={`p-2 rounded-lg ${bgColors[color]}`}>
          <span className={iconColors[color]}>{icon}</span>
        </span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{detail}</p>
    </div>
  )
}

function AgentRow({ agent }: { agent: AgentSummary }) {
  return (
    <li className="flex items-center gap-3 py-2">
      <span className="flex items-center justify-center h-8 w-8 rounded-full bg-primary-100 text-primary-700 text-xs font-medium shrink-0">
        {agent.name.charAt(0)}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900 truncate">{agent.name}</span>
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${AGENT_STATUS_COLORS[agent.status] ?? 'bg-gray-100 text-gray-500'}`}>
            {agent.status}
          </span>
        </div>
        <p className="text-xs text-gray-500 truncate">
          {agent.role}{agent.room_name ? ` · ${agent.room_name}` : ''}
        </p>
      </div>
    </li>
  )
}

function TaskRow({ task }: { task: TaskSummary }) {
  return (
    <li className="py-2.5 first:pt-0 last:pb-0">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{task.title}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {task.agent_name}
            <span className={`ml-2 ${PRIORITY_COLORS[task.priority] ?? 'text-gray-500'}`}>
              {task.priority}
            </span>
          </p>
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0 ${TASK_STATUS_COLORS[task.status] ?? 'bg-gray-100 text-gray-600'}`}>
          {task.status.replace('_', ' ')}
        </span>
      </div>
    </li>
  )
}

function EmptyState({ message, detail }: { message: string; detail: string }) {
  return (
    <div className="text-center py-6">
      <svg className="mx-auto h-8 w-8 text-gray-300" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
      </svg>
      <p className="text-sm text-gray-500 mt-2">{message}</p>
      <p className="text-xs text-gray-400 mt-0.5">{detail}</p>
    </div>
  )
}

function AgentIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
    </svg>
  )
}

function RoomIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3h.008v.008h-.008v-.008Zm0 3h.008v.008h-.008v-.008Zm0 3h.008v.008h-.008v-.008Z" />
    </svg>
  )
}

function TaskIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 6.878V6a2.25 2.25 0 012.25-2.25h7.5A2.25 2.25 0 0118 6v.878m-12 0c.235-.083.487-.128.75-.128h10.5c.263 0 .515.045.75.128m-12 0A2.25 2.25 0 004.5 9v.878m13.5-3A2.25 2.25 0 0119.5 9v.878m0 0a2.246 2.246 0 00-.75-.128H5.25c-.263 0-.515.045-.75.128m15 0A2.25 2.25 0 0121 12v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6c0-.98.626-1.813 1.5-2.122" />
    </svg>
  )
}

function ActionIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

const DashboardPage = () => {
  const user = useAuthStore((s) => s.user)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    const result = await officeService.getDashboardSummary()
    if (result.success && result.data) {
      setSummary(result.data)
    } else {
      setError(result.error ?? 'Failed to load dashboard')
    }
    setIsLoading(false)
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-64 bg-gray-200 rounded animate-pulse mt-2" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="h-4 w-24 bg-gray-200 rounded animate-pulse mb-3" />
              <div className="h-8 w-16 bg-gray-200 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
        <button
          type="button"
          onClick={fetchData}
          className="px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!summary) return null

  const greeting = getGreeting()

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          {greeting}, {user?.name ?? 'CEO'}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Here is what is happening in your company today.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total Agents"
          value={summary.total_agents}
          detail={`${summary.active_agents} active, ${summary.busy_agents} busy`}
          icon={<AgentIcon />}
          color="primary"
        />
        <StatCard
          label="Office Rooms"
          value={summary.total_rooms}
          detail={`${summary.available_rooms} available, ${summary.occupied_rooms} occupied`}
          icon={<RoomIcon />}
          color="emerald"
        />
        <StatCard
          label="Total Tasks"
          value={summary.total_tasks}
          detail={`${summary.completed_tasks} completed`}
          icon={<TaskIcon />}
          color="blue"
        />
        <StatCard
          label="Pending Actions"
          value={summary.pending_tasks + summary.in_progress_tasks}
          detail={`${summary.pending_tasks} pending, ${summary.in_progress_tasks} in progress`}
          icon={<ActionIcon />}
          color="amber"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white rounded-xl border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">Agent Activity</h2>
            <Link
              to="/office"
              className="text-xs font-medium text-primary-600 hover:text-primary-700"
            >
              View Office
            </Link>
          </div>
          <div className="p-5">
            {summary.agents.length === 0 ? (
              <EmptyState
                message="No agents yet"
                detail="Create agents to get started"
              />
            ) : (
              <ul className="space-y-2">
                {summary.agents.map((agent) => (
                  <AgentRow key={agent.id} agent={agent} />
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="bg-white rounded-xl border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Pending Actions</h2>
          </div>
          <div className="p-5">
            {summary.pending_actions.length === 0 ? (
              <EmptyState
                message="No pending actions"
                detail="All tasks are up to date"
              />
            ) : (
              <ul className="divide-y divide-gray-100">
                {summary.pending_actions.map((task) => (
                  <TaskRow key={task.id} task={task} />
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>

      {summary.recent_tasks.length > 0 && (
        <section className="mt-6 bg-white rounded-xl border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Recent Tasks</h2>
          </div>
          <div className="p-5">
            <ul className="divide-y divide-gray-100">
              {summary.recent_tasks.map((task) => (
                <TaskRow key={task.id} task={task} />
              ))}
            </ul>
          </div>
        </section>
      )}
    </div>
  )
}

export default DashboardPage
