import { useState, useEffect } from 'react'
import type { Approval } from '../../types'
import { officeService } from '../../services/office'
import { formatTimeAgo } from '../../lib/utils'
import { X, Clock, Shield, AlertTriangle, CheckCircle, XCircle, RotateCcw, Trash2 } from 'lucide-react'

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: typeof Clock }> = {
  pending: { label: 'Pending', color: 'text-amber-400', bg: 'bg-amber-500/15 border-amber-500/20', icon: Clock },
  approved: { label: 'Approved', color: 'text-green-400', bg: 'bg-green-500/15 border-green-500/20', icon: CheckCircle },
  rejected: { label: 'Rejected', color: 'text-red-400', bg: 'bg-red-500/15 border-red-500/20', icon: XCircle },
  expired: { label: 'Expired', color: 'text-gray-400', bg: 'bg-white/5 border-white/10', icon: Clock },
  cancelled: { label: 'Cancelled', color: 'text-white/40', bg: 'bg-white/5 border-white/10', icon: XCircle },
}

const RISK_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  low: { label: 'Low', color: 'text-green-400', bg: 'bg-green-500/15 border-green-500/20' },
  medium: { label: 'Medium', color: 'text-amber-400', bg: 'bg-amber-500/15 border-amber-500/20' },
  high: { label: 'High', color: 'text-red-400', bg: 'bg-red-500/15 border-red-500/20' },
  critical: { label: 'Critical', color: 'text-red-300', bg: 'bg-red-500/20 border-red-500/30' },
}

interface ApprovalEvent {
  id: string
  event_type: string
  old_status: string | null
  new_status: string | null
  description: string | null
  performed_by: string | null
  created_at: string | null
}

interface ApprovalDetailModalProps {
  approvalId: string
  onClose: () => void
  onApprove?: (id: string) => Promise<{ success: boolean; error?: string }>
  onReject?: (id: string) => Promise<{ success: boolean; error?: string }>
  onCancel?: (id: string) => Promise<{ success: boolean; error?: string }>
  onRetry?: (id: string) => Promise<{ success: boolean; error?: string }>
}

export default function ApprovalDetailModal({ approvalId, onClose, onApprove, onReject, onCancel, onRetry }: ApprovalDetailModalProps) {
  const [approval, setApproval] = useState<Approval | null>(null)
  const [events, setEvents] = useState<ApprovalEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<'approve' | 'reject' | 'cancel' | 'retry' | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [approvalId])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [approvalRes, eventsRes] = await Promise.all([
        officeService.getApproval(approvalId),
        officeService.getApprovalEvents(approvalId)
      ])
      setApproval(approvalRes.data ?? null)
      setEvents(eventsRes.data ?? [])
    } catch (err) {
      setError('Failed to load approval details')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!onApprove) return
    setActionLoading('approve')
    try {
      await onApprove(approvalId)
      await loadData()
    } finally {
      setActionLoading(null)
    }
  }

  const handleReject = async () => {
    if (!onReject) return
    setActionLoading('reject')
    try {
      await onReject(approvalId)
      await loadData()
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancel = async () => {
    if (!onCancel) return
    setActionLoading('cancel')
    try {
      await onCancel(approvalId)
      await loadData()
    } finally {
      setActionLoading(null)
    }
  }

  const handleRetry = async () => {
    if (!onRetry) return
    setActionLoading('retry')
    try {
      await onRetry(approvalId)
      await loadData()
    } finally {
      setActionLoading(null)
    }
  }

  const status = approval ? (STATUS_CONFIG[approval.status] ?? STATUS_CONFIG.pending) : STATUS_CONFIG.pending
  const risk = approval ? (RISK_CONFIG[approval.risk_level] ?? RISK_CONFIG.low) : RISK_CONFIG.low
  const StatusIcon = status.icon
  const isPending = approval?.status === 'pending'
  const canRetry = approval?.status === 'rejected' || approval?.status === 'expired'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-[#0a0a14] rounded-2xl border border-white/10 shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/6 flex items-start justify-between gap-4 shrink-0">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-xl border ${status.bg}`}>
                <StatusIcon size={18} className={status.color} />
              </div>
              <div className="min-w-0">
                <h2 className="text-lg font-bold text-white truncate">
                  {loading ? 'Loading...' : approval?.action}
                </h2>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${status.bg} ${status.color}`}>
                    {status.label}
                  </span>
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${risk.bg} ${risk.color}`}>
                    {risk.label} Risk
                  </span>
                </div>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-white/30 hover:text-white/60 hover:bg-white/5 rounded-lg transition-colors shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {error && (
            <div className="text-center py-12">
              <AlertTriangle size={32} className="text-red-400 mx-auto mb-3" />
              <p className="text-sm text-red-400">{error}</p>
              <button onClick={loadData} className="mt-2 text-xs text-indigo-400 hover:text-indigo-300">
                Try again
              </button>
            </div>
          )}

          {approval && !loading && !error && (
            <div className="space-y-5">
              {/* Description */}
              {approval.description && (
                <div>
                  <h4 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-1.5">Description</h4>
                  <p className="text-sm text-white/70 leading-relaxed">{approval.description}</p>
                </div>
              )}

              {/* Agent Info */}
              <div className="flex items-center gap-3 p-3 rounded-xl bg-white/3 border border-white/6">
                <div className="w-9 h-9 rounded-lg bg-indigo-500/15 border border-indigo-500/20 flex items-center justify-center">
                  <Shield size={16} className="text-indigo-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{approval.agent_name || 'Unknown Agent'}</p>
                  {approval.agent_role && (
                    <p className="text-[11px] text-white/30">{approval.agent_role}</p>
                  )}
                </div>
              </div>

              {/* Parameters */}
              {approval.parameters && Object.keys(approval.parameters).length > 0 && (
                <div>
                  <h4 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-2">Parameters</h4>
                  <div className="rounded-xl bg-white/3 border border-white/6 overflow-hidden">
                    {Object.entries(approval.parameters).map(([key, value], i) => (
                      <div key={key} className={`flex items-start px-3 py-2.5 ${i > 0 ? 'border-t border-white/6' : ''}`}>
                        <span className="text-xs font-medium text-white/40 w-28 shrink-0">{key}</span>
                        <span className="text-xs text-white/70 break-all">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Reason */}
              {approval.reason && (
                <div>
                  <h4 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-1.5">Reason</h4>
                  <p className="text-sm text-white/70 leading-relaxed">{approval.reason}</p>
                </div>
              )}

              {/* Decision Notes */}
              {approval.decision_notes && (
                <div className="p-3 rounded-xl bg-white/3 border border-white/6">
                  <h4 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-1.5">Decision Notes</h4>
                  <p className="text-sm text-white/60">{approval.decision_notes}</p>
                  {approval.decided_by_name && (
                    <p className="text-[11px] text-white/30 mt-1.5">
                      Decided by {approval.decided_by_name}
                      {approval.decided_at && ` ${formatTimeAgo(approval.decided_at)}`}
                    </p>
                  )}
                </div>
              )}

              {/* Timeline */}
              <div>
                <h4 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-2">Timeline</h4>
                <div className="space-y-0">
                  <div className="flex items-center gap-3 text-xs">
                    <div className="w-1.5 h-1.5 rounded-full bg-white/20 shrink-0" />
                    <span className="text-white/40">Requested</span>
                    <span className="text-white/30 ml-auto">
                      {approval.requested_at ? formatTimeAgo(approval.requested_at) : '—'}
                    </span>
                  </div>
                  {approval.decided_at && (
                    <div className="flex items-center gap-3 text-xs mt-2">
                      <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                        approval.status === 'approved' ? 'bg-green-400' :
                        approval.status === 'rejected' ? 'bg-red-400' : 'bg-white/20'
                      }`} />
                      <span className="text-white/40">Decided</span>
                      <span className="text-white/30 ml-auto">{formatTimeAgo(approval.decided_at)}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Event History */}
              {events.length > 0 && (
                <div>
                  <h4 className="text-[11px] font-medium text-white/30 uppercase tracking-wider mb-2">Event History</h4>
                  <div className="space-y-0">
                    {events.map((event) => (
                      <div key={event.id} className="flex items-start gap-3 py-2 border-l border-white/6 ml-[3px] pl-4">
                        <div className="w-1.5 h-1.5 rounded-full bg-white/20 shrink-0 mt-1.5 -ml-[21px]" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium text-white/50">{event.event_type.replace(/_/g, ' ')}</span>
                            {event.old_status && event.new_status && (
                              <span className="text-[10px] text-white/25">
                                {event.old_status} → {event.new_status}
                              </span>
                            )}
                          </div>
                          {event.description && (
                            <p className="text-[11px] text-white/30 mt-0.5">{event.description}</p>
                          )}
                          <div className="flex items-center gap-2 mt-0.5">
                            {event.performed_by && (
                              <span className="text-[10px] text-white/20">by {event.performed_by}</span>
                            )}
                            {event.created_at && (
                              <span className="text-[10px] text-white/20">{formatTimeAgo(event.created_at)}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {approval && !loading && (
          <div className="px-6 py-4 border-t border-white/6 shrink-0">
            <div className="flex items-center gap-2">
              {isPending && onApprove && (
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={actionLoading !== null}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-500 disabled:opacity-50 transition-colors"
                >
                  {actionLoading === 'approve' ? (
                    <div className="animate-spin h-4 w-4 border-2 border-green-300 border-t-white rounded-full" />
                  ) : (
                    <CheckCircle size={15} />
                  )}
                  Approve
                </button>
              )}
              {isPending && onReject && (
                <button
                  type="button"
                  onClick={handleReject}
                  disabled={actionLoading !== null}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg hover:bg-red-500/20 disabled:opacity-50 transition-colors"
                >
                  {actionLoading === 'reject' ? (
                    <div className="animate-spin h-4 w-4 border-2 border-red-300 border-t-red-600 rounded-full" />
                  ) : (
                    <XCircle size={15} />
                  )}
                  Reject
                </button>
              )}
              {isPending && onCancel && (
                <button
                  type="button"
                  onClick={handleCancel}
                  disabled={actionLoading !== null}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-white/40 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 disabled:opacity-50 transition-colors"
                >
                  {actionLoading === 'cancel' ? (
                    <div className="animate-spin h-4 w-4 border-2 border-white/20 border-t-white/60 rounded-full" />
                  ) : (
                    <Trash2 size={15} />
                  )}
                  Cancel
                </button>
              )}
              {canRetry && onRetry && (
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={actionLoading !== null}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg hover:bg-amber-500/20 disabled:opacity-50 transition-colors"
                >
                  {actionLoading === 'retry' ? (
                    <div className="animate-spin h-4 w-4 border-2 border-amber-300 border-t-amber-600 rounded-full" />
                  ) : (
                    <RotateCcw size={15} />
                  )}
                  Retry
                </button>
              )}
              {!isPending && !canRetry && (
                <div className="flex-1 text-center text-xs text-white/30 py-2">
                  No actions available for this approval
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
