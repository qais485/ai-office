import { useState, useEffect } from 'react'
import type { Approval, ApprovalStats } from '../types'
import { officeService } from '../services/office'
import ApprovalDetailModal from '../components/office/ApprovalDetailModal'

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  pending: { label: 'Pending', color: 'bg-amber-500/15 text-amber-300', icon: '⏳' },
  approved: { label: 'Approved', color: 'bg-green-500/15 text-green-300', icon: '✓' },
  rejected: { label: 'Rejected', color: 'bg-red-500/15 text-red-300', icon: '✗' },
  expired: { label: 'Expired', color: 'bg-white/10 text-white/60', icon: '⏰' },
  cancelled: { label: 'Cancelled', color: 'bg-white/10 text-white/50', icon: '⊘' },
}

const RISK_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: 'Low', color: 'bg-green-500/15 text-green-300' },
  medium: { label: 'Medium', color: 'bg-amber-500/15 text-amber-300' },
  high: { label: 'High', color: 'bg-red-500/15 text-red-300' },
  critical: { label: 'Critical', color: 'bg-red-500/25 text-red-300' },
}

function ApprovalCard({ approval, onApprove, onReject, onCancel, onRetry, onSelect }: {
  approval: Approval
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onCancel: (id: string) => void
  onRetry: (id: string) => void
  onSelect: (approval: Approval) => void
}) {
  const status = STATUS_CONFIG[approval.status] || STATUS_CONFIG.pending
  const risk = RISK_CONFIG[approval.risk_level] || RISK_CONFIG.low
  const isPending = approval.status === 'pending'
  const canRetry = approval.status === 'rejected' || approval.status === 'expired'

  return (
    <div
      onClick={() => onSelect(approval)}
      className="bg-white/[0.03] rounded-xl border border-white/10 p-5 hover:bg-white/[0.05] hover:border-white/15 transition-colors cursor-pointer"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg ${status.color}`}>
            {status.icon}
          </div>
          <div>
            <h3 className="font-semibold text-white">{approval.action}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${status.color}`}>
                {status.label}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${risk.color}`}>
                {risk.label} Risk
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-2 mb-4">
        <div className="flex items-center text-sm">
          <span className="text-white/50 w-20">Agent:</span>
          <span className="font-medium text-white">{approval.agent_name || 'Unknown'}</span>
          {approval.agent_role && (
            <span className="text-white/40 ml-1">({approval.agent_role})</span>
          )}
        </div>
        {approval.parameters && Object.keys(approval.parameters).length > 0 && (
          <div className="flex items-start text-sm">
            <span className="text-white/50 w-20">Details:</span>
            <div className="flex-1">
              {Object.entries(approval.parameters).map(([key, value]) => (
                <div key={key} className="text-white/80">
                  <span className="font-medium">{key}:</span> {String(value)}
                </div>
              ))}
            </div>
          </div>
        )}
        {approval.reason && (
          <div className="flex items-start text-sm">
            <span className="text-white/50 w-20">Reason:</span>
            <span className="text-white/80">{approval.reason}</span>
          </div>
        )}
      </div>

      {approval.decision_notes && (
        <div className="bg-white/[0.04] rounded-lg p-3 mb-4">
          <p className="text-sm text-white/70">
            <span className="font-medium">Decision Notes:</span> {approval.decision_notes}
          </p>
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-white/6">
        <span className="text-xs text-white/40">
          {approval.requested_at && new Date(approval.requested_at).toLocaleString()}
        </span>
        <div className="flex items-center gap-2">
          {isPending && (
            <>
              <button
                onClick={() => onApprove(approval.id)}
                className="px-3 py-1.5 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-500 transition-colors"
              >
                Approve
              </button>
              <button
                onClick={() => onReject(approval.id)}
                className="px-3 py-1.5 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-500 transition-colors"
              >
                Reject
              </button>
              <button
                onClick={() => onCancel(approval.id)}
                className="px-3 py-1.5 bg-white/10 text-white/80 text-sm font-medium rounded-lg hover:bg-white/15 transition-colors"
              >
                Cancel
              </button>
            </>
          )}
          {canRetry && (
            <button
              onClick={() => onRetry(approval.id)}
              className="px-3 py-1.5 bg-amber-500/15 text-amber-300 text-sm font-medium rounded-lg hover:bg-amber-500/20 transition-colors"
            >
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [stats, setStats] = useState<ApprovalStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)
  const [filterRisk, setFilterRisk] = useState<string | null>(null)
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null)

  useEffect(() => {
    loadData()
  }, [filterStatus, filterRisk])

  const loadData = async () => {
    try {
      setLoading(true)
      const [approvalsRes, statsRes] = await Promise.all([
        officeService.getApprovals(filterStatus || undefined, undefined, filterRisk || undefined),
        officeService.getApprovalStats()
      ])
      setApprovals(approvalsRes.data ?? [])
      setStats(statsRes.data ?? null)
    } catch (err) {
      setError('Failed to load approvals')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (id: string) => {
    try {
      await officeService.approveApproval(id, 'Approved by CEO')
      await loadData()
    } catch (err) {
      console.error('Failed to approve:', err)
    }
  }

  const handleReject = async (id: string) => {
    try {
      await officeService.rejectApproval(id, 'Rejected by CEO')
      await loadData()
    } catch (err) {
      console.error('Failed to reject:', err)
    }
  }

  const handleCancel = async (id: string) => {
    try {
      await officeService.cancelApproval(id)
      await loadData()
    } catch (err) {
      console.error('Failed to cancel:', err)
    }
  }

  const handleRetry = async (id: string) => {
    try {
      await officeService.retryApproval(id)
      await loadData()
    } catch (err) {
      console.error('Failed to retry:', err)
    }
  }

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-white/10 border-t-indigo-400 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-white/40">Loading approvals...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-400 mb-2">{error}</p>
          <button onClick={loadData} className="text-sm text-indigo-400 hover:text-indigo-300">
            Try again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Approval Center</h1>
            <p className="text-white/50 mt-1">Review and manage agent approval requests</p>
          </div>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-5 gap-4 mb-8">
          <button
            onClick={() => setFilterStatus(null)}
            className={`p-4 rounded-xl border transition-colors ${
              !filterStatus
                ? 'bg-indigo-500/10 border-indigo-500/30'
                : 'bg-white/[0.03] border-white/10 hover:border-white/20'
            }`}
          >
            <div className="text-2xl font-bold text-white">{stats.total}</div>
            <div className="text-sm text-white/50">Total</div>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'pending' ? null : 'pending')}
            className={`p-4 rounded-xl border transition-colors ${
              filterStatus === 'pending'
                ? 'bg-amber-500/10 border-amber-500/25'
                : 'bg-white/[0.03] border-white/10 hover:border-white/20'
            }`}
          >
            <div className="text-2xl font-bold text-amber-400">{stats.pending}</div>
            <div className="text-sm text-white/50">Pending</div>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'approved' ? null : 'approved')}
            className={`p-4 rounded-xl border transition-colors ${
              filterStatus === 'approved'
                ? 'bg-green-500/10 border-green-500/25'
                : 'bg-white/[0.03] border-white/10 hover:border-white/20'
            }`}
          >
            <div className="text-2xl font-bold text-green-400">{stats.approved}</div>
            <div className="text-sm text-white/50">Approved</div>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'rejected' ? null : 'rejected')}
            className={`p-4 rounded-xl border transition-colors ${
              filterStatus === 'rejected'
                ? 'bg-red-500/10 border-red-500/25'
                : 'bg-white/[0.03] border-white/10 hover:border-white/20'
            }`}
          >
            <div className="text-2xl font-bold text-red-400">{stats.rejected}</div>
            <div className="text-sm text-white/50">Rejected</div>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'expired' ? null : 'expired')}
            className={`p-4 rounded-xl border transition-colors ${
              filterStatus === 'expired'
                ? 'bg-white/[0.06] border-white/15'
                : 'bg-white/[0.03] border-white/10 hover:border-white/20'
            }`}
          >
            <div className="text-2xl font-bold text-white/70">{stats.expired}</div>
            <div className="text-sm text-white/50">Expired</div>
          </button>
        </div>
      )}

      <div className="mb-6">
        <div className="flex items-center gap-4">
          <div className="flex gap-2">
            <span className="text-sm text-white/50 py-1.5">Risk Level:</span>
            {['low', 'medium', 'high', 'critical'].map((risk) => {
              const config = RISK_CONFIG[risk]
              return (
                <button
                  key={risk}
                  onClick={() => setFilterRisk(filterRisk === risk ? null : risk)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                    filterRisk === risk
                      ? `${config.color}`
                      : 'bg-white/10 text-white/60 hover:bg-white/15'
                  }`}
                >
                  {config.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {approvals.map((approval) => (
          <ApprovalCard
            key={approval.id}
            approval={approval}
            onApprove={handleApprove}
            onReject={handleReject}
            onCancel={handleCancel}
            onRetry={handleRetry}
            onSelect={setSelectedApproval}
          />
        ))}
      </div>

      {approvals.length === 0 && (
        <div className="text-center py-12">
          <p className="text-white/40">No approvals found</p>
        </div>
      )}

      {selectedApproval && (
        <ApprovalDetailModal
          approvalId={selectedApproval.id}
          onClose={() => setSelectedApproval(null)}
          onApprove={async (id) => { await handleApprove(id); return { success: true }; }}
          onReject={async (id) => { await handleReject(id); return { success: true }; }}
          onCancel={async (id) => { await handleCancel(id); return { success: true }; }}
          onRetry={async (id) => { await handleRetry(id); return { success: true }; }}
        />
      )}
    </div>
  )
}
