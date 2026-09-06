import { useState, useEffect, useCallback } from 'react'
import type { RiskRule, RiskSummary, AgentTool } from '../types'
import { officeService } from '../services/office'

const RISK_LEVELS: Record<string, { label: string; color: string; description: string }> = {
  low: { label: 'Low', color: 'bg-green-100 text-green-700', description: 'Auto-approved, logged' },
  medium: { label: 'Medium', color: 'bg-amber-100 text-amber-700', description: 'Auto-approved, logged' },
  high: { label: 'High', color: 'bg-red-100 text-red-700', description: 'Requires CEO approval' },
  critical: { label: 'Critical', color: 'bg-red-200 text-red-800', description: 'Requires CEO approval + 2FA' },
}

function Toast({ message, type, onClose }: { message: string; type: 'error' | 'success'; onClose: () => void }) {
  return (
    <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium ${
      type === 'error' ? 'bg-red-600 text-white' : 'bg-green-600 text-white'
    }`}>
      <div className="flex items-center gap-2">
        <span>{message}</span>
        <button onClick={onClose} className="ml-2 text-white/80 hover:text-white">&times;</button>
      </div>
    </div>
  )
}

function ConfirmDialog({ title, message, onConfirm, onCancel }: {
  title: string
  message: string
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-sm">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
        <p className="text-sm text-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
            Cancel
          </button>
          <button onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors">
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}

function RiskRuleCard({ rule, tools, onEdit, onDelete, onToggle }: {
  rule: RiskRule
  tools: AgentTool[]
  onEdit: (rule: RiskRule) => void
  onDelete: (id: string) => void
  onToggle: (id: string, isActive: boolean) => void
}) {
  const risk = RISK_LEVELS[rule.risk_level] || RISK_LEVELS.medium
  const tool = tools.find(t => t.id === rule.tool_id)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg ${risk.color}`}>
            {rule.risk_level === 'critical' ? '🔴' : rule.risk_level === 'high' ? '🟠' : rule.risk_level === 'medium' ? '🟡' : '🟢'}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{rule.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${risk.color}`}>
                {risk.label}
              </span>
              {rule.requires_approval && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
                  Requires Approval
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onToggle(rule.id, !rule.is_active)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              rule.is_active ? 'bg-primary-600' : 'bg-gray-200'
            }`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              rule.is_active ? 'translate-x-6' : 'translate-x-1'
            }`} />
          </button>
        </div>
      </div>

      {rule.description && (
        <p className="text-sm text-gray-600 mb-3">{rule.description}</p>
      )}

      <div className="space-y-2 mb-4">
        {rule.action_name && (
          <div className="flex items-center text-sm">
            <span className="text-gray-500 w-24">Action:</span>
            <span className="font-medium text-gray-900">{rule.action_name}</span>
          </div>
        )}
        {tool && (
          <div className="flex items-center text-sm">
            <span className="text-gray-500 w-24">Tool:</span>
            <span className="font-medium text-gray-900">{tool.display_name}</span>
          </div>
        )}
        {rule.conditions && Object.keys(rule.conditions).length > 0 && (
          <div className="flex items-start text-sm">
            <span className="text-gray-500 w-24">Conditions:</span>
            <div className="flex-1">
              {Object.entries(rule.conditions).map(([key, value]) => (
                <div key={key} className="text-gray-700">
                  <span className="font-medium">{key}:</span> {JSON.stringify(value)}
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="flex items-center text-sm">
          <span className="text-gray-500 w-24">Priority:</span>
          <span className="font-medium text-gray-900">{rule.priority}</span>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-100">
        <button
          onClick={() => onEdit(rule)}
          className="px-3 py-1.5 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          Edit
        </button>
        <button
          onClick={() => onDelete(rule.id)}
          className="px-3 py-1.5 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
  )
}

function RiskRuleForm({ rule, tools, onSave, onCancel, saving }: {
  rule?: RiskRule
  tools: AgentTool[]
  onSave: (data: Partial<RiskRule>) => void
  onCancel: () => void
  saving: boolean
}) {
  const [name, setName] = useState(rule?.name || '')
  const [description, setDescription] = useState(rule?.description || '')
  const [actionName, setActionName] = useState(rule?.action_name || '')
  const [toolId, setToolId] = useState(rule?.tool_id || '')
  const [riskLevel, setRiskLevel] = useState(rule?.risk_level || 'medium')
  const [requiresApproval, setRequiresApproval] = useState(rule?.requires_approval || false)
  const [priority, setPriority] = useState(rule?.priority || 0)
  const [conditionsText, setConditionsText] = useState(
    rule?.conditions ? JSON.stringify(rule.conditions, null, 2) : ''
  )
  const [conditionsError, setConditionsError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    let conditions: Record<string, unknown> | undefined
    if (conditionsText.trim()) {
      try {
        conditions = JSON.parse(conditionsText)
        setConditionsError(null)
      } catch {
        setConditionsError('Invalid JSON. Use format: {"key": {"min": 0, "max": 100}}')
        return
      }
    }

    onSave({
      name,
      description: description || undefined,
      action_name: actionName || undefined,
      tool_id: toolId || undefined,
      risk_level: riskLevel,
      requires_approval: requiresApproval,
      priority,
      conditions: conditions || undefined,
      is_active: rule?.is_active ?? true,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {rule ? 'Edit Risk Rule' : 'Create Risk Rule'}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Action Name</label>
            <input
              type="text"
              value={actionName}
              onChange={(e) => setActionName(e.target.value)}
              placeholder="e.g., issue_refund"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tool</label>
            <select
              value={toolId}
              onChange={(e) => setToolId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="">All tools</option>
              {tools.map(tool => (
                <option key={tool.id} value={tool.id}>{tool.display_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Risk Level</label>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(RISK_LEVELS).map(([key, config]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    setRiskLevel(key)
                    if (key === 'high' || key === 'critical') {
                      setRequiresApproval(true)
                    }
                  }}
                  className={`p-3 rounded-lg border-2 text-left transition-colors ${
                    riskLevel === key
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="font-medium text-sm">{config.label}</div>
                  <div className="text-xs text-gray-500">{config.description}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="block text-sm font-medium text-gray-700">Requires Approval</label>
              <p className="text-xs text-gray-500">CEO must approve before execution</p>
            </div>
            <button
              type="button"
              onClick={() => setRequiresApproval(!requiresApproval)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                requiresApproval ? 'bg-primary-600' : 'bg-gray-200'
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                requiresApproval ? 'translate-x-6' : 'translate-x-1'
              }`} />
            </button>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
            <input
              type="number"
              value={priority}
              onChange={(e) => setPriority(parseInt(e.target.value) || 0)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
            <p className="text-xs text-gray-500 mt-1">Higher priority rules are checked first</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Conditions (JSON)</label>
            <textarea
              value={conditionsText}
              onChange={(e) => { setConditionsText(e.target.value); setConditionsError(null) }}
              rows={4}
              placeholder={'{"amount": {"min": 100, "max": 10000}, "type": "refund"}'}
              className={`w-full px-3 py-2 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${
                conditionsError ? 'border-red-300' : 'border-gray-300'
              }`}
            />
            {conditionsError && (
              <p className="text-xs text-red-600 mt-1">{conditionsError}</p>
            )}
            <p className="text-xs text-gray-500 mt-1">Supported operators: min, max, equals, contains</p>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : rule ? 'Save Changes' : 'Create Rule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function RiskSettingsPage() {
  const [rules, setRules] = useState<RiskRule[]>([])
  const [summary, setSummary] = useState<RiskSummary | null>(null)
  const [tools, setTools] = useState<AgentTool[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingRule, setEditingRule] = useState<RiskRule | undefined>()
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'error' | 'success' } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const showToast = useCallback((message: string, type: 'error' | 'success' = 'error') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 4000)
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [rulesRes, summaryRes, toolsRes] = await Promise.all([
        officeService.getRiskRules(false),
        officeService.getRiskSummary(),
        officeService.getTools()
      ])
      setRules(rulesRes.data ?? [])
      setSummary(summaryRes.data ?? null)
      setTools(toolsRes.data ?? [])
    } catch (err) {
      setError('Failed to load risk rules')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (data: Partial<RiskRule>) => {
    try {
      setSaving(true)
      await officeService.createRiskRule(data)
      setShowForm(false)
      showToast('Rule created', 'success')
      await loadData()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create rule'
      showToast(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async (data: Partial<RiskRule>) => {
    if (!editingRule) return
    try {
      setSaving(true)
      await officeService.updateRiskRule(editingRule.id, data)
      setEditingRule(undefined)
      setShowForm(false)
      showToast('Rule updated', 'success')
      await loadData()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to update rule'
      showToast(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirmDelete) return
    try {
      await officeService.deleteRiskRule(confirmDelete)
      setConfirmDelete(null)
      showToast('Rule deleted', 'success')
      await loadData()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to delete rule'
      showToast(msg)
    }
  }

  const handleToggle = async (id: string, isActive: boolean) => {
    try {
      await officeService.updateRiskRule(id, { is_active: isActive })
      await loadData()
    } catch (err) {
      showToast('Failed to toggle rule')
    }
  }

  const openCreateForm = () => {
    setEditingRule(undefined)
    setShowForm(true)
  }

  const openEditForm = (rule: RiskRule) => {
    setEditingRule(rule)
    setShowForm(true)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading risk rules...</p>
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
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {confirmDelete && (
        <ConfirmDialog
          title="Delete Risk Rule"
          message="This action cannot be undone. The rule will be permanently removed."
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(null)}
        />
      )}

      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Risk Settings</h1>
            <p className="text-gray-500 mt-1">Configure risk rules for AI agent actions</p>
          </div>
          <button
            onClick={openCreateForm}
            className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors"
          >
            + Add Rule
          </button>
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-4 mb-8">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-2xl font-bold text-gray-900">{summary.total_rules}</div>
            <div className="text-sm text-gray-500">Total Rules</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-2xl font-bold text-green-600">{summary.by_risk_level.low}</div>
            <div className="text-sm text-gray-500">Low Risk</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-2xl font-bold text-amber-600">{summary.by_risk_level.medium}</div>
            <div className="text-sm text-gray-500">Medium Risk</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-2xl font-bold text-red-600">{summary.by_risk_level.high}</div>
            <div className="text-sm text-gray-500">High Risk</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-2xl font-bold text-red-800">{summary.by_risk_level.critical}</div>
            <div className="text-sm text-gray-500">Critical</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {rules.map((rule) => (
          <RiskRuleCard
            key={rule.id}
            rule={rule}
            tools={tools}
            onEdit={openEditForm}
            onDelete={(id) => setConfirmDelete(id)}
            onToggle={handleToggle}
          />
        ))}
      </div>

      {rules.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No risk rules configured</p>
          <button
            onClick={openCreateForm}
            className="mt-4 text-sm text-primary-600 hover:text-primary-700"
          >
            Create your first rule
          </button>
        </div>
      )}

      {showForm && (
        <RiskRuleForm
          rule={editingRule}
          tools={tools}
          saving={saving}
          onSave={editingRule ? handleUpdate : handleCreate}
          onCancel={() => {
            setShowForm(false)
            setEditingRule(undefined)
          }}
        />
      )}
    </div>
  )
}
