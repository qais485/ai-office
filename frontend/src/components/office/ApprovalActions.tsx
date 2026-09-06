import { useState } from 'react'
import type { Approval } from '../../types'
import { formatTimeAgo } from '../../lib/utils'

const RISK_COLORS: Record<string, string> = {
  low: 'bg-green-500/15 text-green-400 border border-green-500/20',
  medium: 'bg-amber-500/15 text-amber-400 border border-amber-500/20',
  high: 'bg-red-500/15 text-red-400 border border-red-500/20',
  critical: 'bg-red-500/20 text-red-300 border border-red-500/30',
}

interface ApprovalActionsProps {
  approvals: Approval[]
  onApprove: (id: string) => Promise<{ success: boolean; error?: string }>
  onReject: (id: string) => Promise<{ success: boolean; error?: string }>
  onSelect?: (approval: Approval) => void
}

export default function ApprovalActions({ approvals, onApprove, onReject, onSelect }: ApprovalActionsProps) {
  const [loadingApprovals, setLoadingApprovals] = useState<Record<string, 'approve' | 'reject' | null>>({})

  const handleApprove = async (id: string) => {
    setLoadingApprovals(prev => ({ ...prev, [id]: 'approve' }))
    try {
      await onApprove(id)
    } finally {
      setLoadingApprovals(prev => ({ ...prev, [id]: null }))
    }
  }

  const handleReject = async (id: string) => {
    setLoadingApprovals(prev => ({ ...prev, [id]: 'reject' }))
    try {
      await onReject(id)
    } finally {
      setLoadingApprovals(prev => ({ ...prev, [id]: null }))
    }
  }

  if (approvals.length === 0) {
    return (
      <div className="rounded-xl bg-white/3 border border-white/6 p-5">
        <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider mb-4">Pending Approvals</h3>
        <div className="text-center py-6">
          <div className="inline-flex items-center justify-center h-10 w-10 rounded-xl bg-green-500/10 border border-green-500/20 mb-2">
            <svg className="h-5 w-5 text-green-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <p className="text-sm text-white/30">No pending approvals</p>
          <p className="text-xs text-white/20 mt-0.5">All clear</p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl bg-white/3 border border-white/6 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-medium text-white/30 uppercase tracking-wider">Pending Approvals</h3>
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-400">
          {approvals.length}
        </span>
      </div>

      <div className="space-y-3">
        {approvals.map((approval) => (
          <div
            key={approval.id}
            onClick={() => onSelect?.(approval)}
            className={`p-3 rounded-lg border border-white/6 hover:border-white/10 transition-all ${onSelect ? 'cursor-pointer hover:bg-white/3' : ''}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-white truncate">{approval.action}</p>
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full shrink-0 ${RISK_COLORS[approval.risk_level] ?? 'bg-white/5 text-white/40 border border-white/10'}`}>
                    {approval.risk_level}
                  </span>
                </div>
                {approval.description && (
                  <p className="text-xs text-white/40 mt-1 line-clamp-2">{approval.description}</p>
                )}
                <div className="flex items-center gap-3 mt-2 text-[10px] text-white/20">
                  <span>{formatTimeAgo(approval.requested_at)}</span>
                  {approval.agent_name && (
                    <span>{approval.agent_name}</span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex gap-2 mt-3">
              <button
                type="button"
                onClick={() => handleApprove(approval.id)}
                disabled={loadingApprovals[approval.id] !== null && loadingApprovals[approval.id] !== undefined}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-green-600 rounded-lg hover:bg-green-500 disabled:opacity-50 transition-colors"
              >
                {loadingApprovals[approval.id] === 'approve' ? (
                  <div className="animate-spin h-3 w-3 border-2 border-green-300 border-t-white rounded-full" />
                ) : (
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                )}
                Approve
              </button>
              <button
                type="button"
                onClick={() => handleReject(approval.id)}
                disabled={loadingApprovals[approval.id] !== null && loadingApprovals[approval.id] !== undefined}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg hover:bg-red-500/20 disabled:opacity-50 transition-colors"
              >
                {loadingApprovals[approval.id] === 'reject' ? (
                  <div className="animate-spin h-3 w-3 border-2 border-red-300 border-t-red-600 rounded-full" />
                ) : (
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
