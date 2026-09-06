import type { AIAgent } from '../../types'
import { formatTimeAgo, parseServerDate } from '../../lib/utils'

const AGENT_STATUS_BADGE: Record<string, string> = {
  active: 'bg-green-500/15 text-green-400 border border-green-500/20',
  paused: 'bg-amber-500/15 text-amber-400 border border-amber-500/20',
  inactive: 'bg-white/5 text-white/40 border border-white/10',
  error: 'bg-red-500/15 text-red-400 border border-red-500/20',
  disabled: 'bg-red-500/10 text-red-400/60 border border-red-500/10',
  draft: 'bg-white/5 text-white/30 border border-white/8',
  archived: 'bg-white/5 text-white/20 border border-white/8',
}

interface LifecycleControlsProps {
  agent: AIAgent
  onAction: (action: 'pause' | 'resume' | 'disable' | 'archive' | 'restart', reason?: string) => Promise<{ success: boolean; error?: string }>
  actionLoading: string | null
}

export default function LifecycleControls({ agent, onAction, actionLoading }: LifecycleControlsProps) {
  const isActive = agent.lifecycle_status === 'active'
  const isPaused = agent.lifecycle_status === 'paused'
  const isError = agent.lifecycle_status === 'error'
  const isDisabled = agent.lifecycle_status === 'disabled'
  const isArchived = agent.lifecycle_status === 'archived'
  const canDisable = !isDisabled && !isArchived

  const controls = [
    {
      action: 'pause' as const,
      label: 'Pause',
      description: 'Temporarily stop agent',
      show: isActive,
      color: 'amber',
    },
    {
      action: 'resume' as const,
      label: 'Resume',
      description: 'Resume agent operations',
      show: isPaused,
      color: 'green',
    },
    {
      action: 'disable' as const,
      label: 'Disable',
      description: 'Disable this agent',
      show: canDisable,
      color: 'red',
    },
    {
      action: 'restart' as const,
      label: 'Restart',
      description: 'Restart after error',
      show: isError || isDisabled,
      color: 'blue',
    },
  ]

  const colorClasses: Record<string, { bg: string; text: string; hover: string; spin: string }> = {
    amber: { bg: 'bg-amber-500/10 border border-amber-500/20', text: 'text-amber-400', hover: 'hover:bg-amber-500/20', spin: 'border-amber-300 border-t-amber-500' },
    green: { bg: 'bg-green-500/10 border border-green-500/20', text: 'text-green-400', hover: 'hover:bg-green-500/20', spin: 'border-green-300 border-t-green-500' },
    red: { bg: 'bg-red-500/10 border border-red-500/20', text: 'text-red-400', hover: 'hover:bg-red-500/20', spin: 'border-red-300 border-t-red-500' },
    blue: { bg: 'bg-blue-500/10 border border-blue-500/20', text: 'text-blue-400', hover: 'hover:bg-blue-500/20', spin: 'border-blue-300 border-t-blue-500' },
  }

  return (
    <div className="rounded-xl bg-white/3 border border-white/6 p-5">
      <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider mb-4">Agent Controls</h3>

      {/* Current Status */}
      <div className="flex items-center justify-between p-3 bg-white/3 rounded-lg border border-white/6 mb-4">
        <span className="text-sm text-white/40">Current Status</span>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${AGENT_STATUS_BADGE[agent.lifecycle_status] ?? AGENT_STATUS_BADGE.inactive}`}>
          {agent.lifecycle_status}
        </span>
      </div>

      {/* Control Buttons */}
      <div className="grid grid-cols-2 gap-3">
        {controls.filter(c => c.show).map((ctrl) => {
          const colors = colorClasses[ctrl.color]
          const isLoading = actionLoading === `${agent.id}-${ctrl.action}`

          return (
            <button
              key={ctrl.action}
              type="button"
              onClick={() => onAction(ctrl.action)}
              disabled={actionLoading !== null}
              className={`flex flex-col items-center gap-1.5 p-4 rounded-xl ${colors.bg} ${colors.text} ${colors.hover} disabled:opacity-50 transition-all`}
            >
              {isLoading ? (
                <div className={`animate-spin h-5 w-5 border-2 ${colors.spin} rounded-full`} />
              ) : (
                <span className="text-sm font-medium">{ctrl.label}</span>
              )}
              <span className="text-[10px] opacity-60 text-center leading-tight">{ctrl.description}</span>
            </button>
          )
        })}
      </div>

      {/* Agent Info */}
      <div className="mt-4 pt-4 border-t border-white/6 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-white/30">Last Active</span>
          <span className="font-medium text-white/60">{agent.last_active_at ? formatTimeAgo(agent.last_active_at) : 'Never'}</span>
        </div>
        {agent.hired_at && (
          <div className="flex justify-between text-sm">
            <span className="text-white/30">Hired</span>
            <span className="font-medium text-white/60">{parseServerDate(agent.hired_at)?.toLocaleDateString() ?? '—'}</span>
          </div>
        )}
        {agent.paused_at && (
          <div className="flex justify-between text-sm">
            <span className="text-white/30">Paused Since</span>
            <span className="font-medium text-amber-400">{formatTimeAgo(agent.paused_at)}</span>
          </div>
        )}
        {agent.disabled_at && (
          <div className="flex justify-between text-sm">
            <span className="text-white/30">Disabled Since</span>
            <span className="font-medium text-red-400">{formatTimeAgo(agent.disabled_at)}</span>
          </div>
        )}
      </div>
    </div>
  )
}
