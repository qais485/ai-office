import { useState, useEffect } from 'react'
import type { Approval, ApprovalStats } from '../types'
import { officeService } from '../services/office'
import ApprovalDetailModal from '../components/office/ApprovalDetailModal'

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  pending: { label: 'Pending', color: 'bg-amber-100 text-amber-700', icon: '⏳' },
  approved: { label: 'Approved', color: 'bg-green-100 text-green-700', icon: '✓' },
  rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700', icon: '✗' },
  expired: { label: 'Expired', color: 'bg-gray-100 text-gray-600', icon: '⏰' },
  cancelled: { label: 'Cancelled', color: 'bg-gray-100 text-gray-500', icon: '⊘' },
}

const RISK_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: 'Low', color: 'bg-green-100 text-green-700' },
  medium: { label: 'Medium', color: 'bg-amber-100 text-amber-700' },
  high: { label: 'High', color: 'bg-red-100 text-red-700' },
  critical: { label: 'Critical', color: 'bg-red-200 text-red-800' },
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
      className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg ${status.color}`}>
            {status.icon}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{approval.action}</h3>
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
          <span className="text-gray-500 w-20">Agent:</span>
          <span className="font-medium text-gray-900">{approval.agent_name || 'Unknown'}</span>
          {approval.agent_role && (
            <span className="text-gray-400 ml-1">({approval.agent_role})</span>
          )}
        </div>
        {approval.parameters && Object.keys(approval.parameters).length > 0 && (
          <div className="flex items-start text-sm">
            <span className="text-gray-500 w-20">Details:</span>
            <div className="flex-1">
              {Object.entries(approval.parameters).map(([key, value]) => (
                <div key={key} className="text-gray-700">
                  <span className="font-medium">{key}:</span> {String(value)}
                </div>
              ))}
            </div>
          </div>
        )}
        {approval.reason && (
          <div className="flex items-start text-sm">
            <span className="text-gray-500 w-20">Reason:</span>
            <span className="text-gray-700">{approval.reason}</span>
          </div>
        )}
      </div>

      {approval.decision_notes && (
        <div className="bg-gray-50 rounded-lg p-3 mb-4">
          <p className="text-sm text-gray-600">
            <span className="font-medium">Decision Notes:</span> {approval.decision_notes}
          </p>
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">
          {approval.requested_at && new Date(approval.requested_at).toLocaleString()}
        </span>
        <div className="flex items-center gap-2">
          {isPending && (
            <>
              <button
                onClick={() => onApprove(approval.id)}
                className="px-3 py-1.5 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors"
              >
                Approve
              </button>
              <button
                onClick={() => onReject(approval.id)}
                className="px-3 py-1.5 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors"
              >
                Reject
              </button>
              <button
                onClick={() => onCancel(approval.id)}
                className="px-3 py-1.5 bg-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
            </>
          )}
          {canRetry && (
            <button
              onClick={() => onRetry(approval.id)}
              className="px-3 py-1.5 bg-amber-100 text-amber-700 text-sm font-medium rounded-lg hover:bg-amber-200 transition-colors"
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
      setApprovals(approvalsRes.data)
      setStats(statsRes.data)
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
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading approvals...</p>
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Approval Center</h1>
            <p className="text-gray-500 mt-1">Review and manage agent approval requests</p>
          </div>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-5 gap-4 mb-8">
          <button
            onClick={() => setFilterStatus(null)}
            className={`p-4 rounded-xl border transition-colors ${
              !filterStatus
                ? 'bg-primary-50 border-primary-200'
                : 'bg-white border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="text-2xl font-bold text-gray-900">{stats.total}</div>
            <div className="text-sm text-gray-500">Total</div>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'pending' ? null : 'pending')}
            className={`p-4 rounded-xl border transition-colors ${
              filterStatus === 'pending'
                ? 'bg-amber-50 border-amber-200'
                : 'bg-white border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="text-2xl font-bold text-amber-600">{stats.pending}</div>
            <div className="text-sm text-gray-500">Pending</div>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'approved' ? null : 'approved')}
            className={`p-4 rounded-xl border transition-colors ${
              filterStatus === 'approved'
                ? 'bg-green-50 border-green-200'
                : 'bg-white border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="text-2xl font-bold text-green-600">{stats.approved}</div>
            <div className="text-sm text-gray-500">Approved</div>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'rejected' ? null : 'rejected')}
            className={`p-4 rounded-xl border transition-colors ${
              filterStatus === 'rejected'
                ? 'bg-red-50 border-red-200'
                : 'bg-white border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="text-2xl font-bold text-red-600">{stats.rejected}</div>
            <div className="text-sm text-gray-500">Rejected</div>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'expired' ? null : 'expired')}
            className={`p-4 rounded-xl border transition-colors ${
              filterStatus === 'expired'
                ? 'bg-gray-50 border-gray-200'
                : 'bg-white border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="text-2xl font-bold text-gray-600">{stats.expired}</div>
            <div className="text-sm text-gray-500">Expired</div>
          </button>
        </div>
      )}

      <div className="mb-6">
        <div className="flex items-center gap-4">
          <div className="flex gap-2">
            <span className="text-sm text-gray-500 py-1.5">Risk Level:</span>
            {['low', 'medium', 'high', 'critical'].map((risk) => {
              const config = RISK_CONFIG[risk]
              return (
                <button
                  key={risk}
                  onClick={() => setFilterRisk(filterRisk === risk ? null : risk)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                    filterRisk === risk
                      ? `${config.color}`
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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
          <p className="text-gray-500">No approvals found</p>
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
