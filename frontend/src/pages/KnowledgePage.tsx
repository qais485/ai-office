import { useState, useEffect } from 'react'
import type { Knowledge, KnowledgeStats, KnowledgeAgentAccess, AIAgent } from '../types'
import { officeService } from '../services/office'

const CATEGORY_CONFIG: Record<string, { label: string; color: string }> = {
  products: { label: 'Products', color: 'bg-blue-100 text-blue-700' },
  services: { label: 'Services', color: 'bg-purple-100 text-purple-700' },
  pricing: { label: 'Pricing', color: 'bg-green-100 text-green-700' },
  policies: { label: 'Policies', color: 'bg-amber-100 text-amber-700' },
  faq: { label: 'FAQ', color: 'bg-cyan-100 text-cyan-700' },
  brand_voice: { label: 'Brand Voice', color: 'bg-pink-100 text-pink-700' },
  internal_documents: { label: 'Internal Docs', color: 'bg-gray-100 text-gray-700' },
  customer_info: { label: 'Customer Info', color: 'bg-teal-100 text-teal-700' },
  general: { label: 'General', color: 'bg-gray-100 text-gray-600' },
}

const SOURCE_TYPE_CONFIG: Record<string, { label: string; icon: string }> = {
  pdf: { label: 'PDF', icon: '📄' },
  document: { label: 'Document', icon: '📝' },
  text: { label: 'Text', icon: '📃' },
  url: { label: 'URL', icon: '🔗' },
  note: { label: 'Note', icon: '📋' },
  faq: { label: 'FAQ', icon: '❓' },
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  active: { label: 'Active', color: 'bg-green-100 text-green-700' },
  processing: { label: 'Processing', color: 'bg-amber-100 text-amber-700' },
  inactive: { label: 'Inactive', color: 'bg-gray-100 text-gray-600' },
  error: { label: 'Error', color: 'bg-red-100 text-red-700' },
}

function CreateKnowledgeModal({ isOpen, onClose, onSubmit }: {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: { name: string; description?: string; category: string; content?: string; source_type: string; tags?: string[] }) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('general')
  const [sourceType, setSourceType] = useState('note')
  const [content, setContent] = useState('')
  const [tags, setTags] = useState('')

  if (!isOpen) return null

  const handleSubmit = () => {
    if (!name.trim()) return
    onSubmit({
      name: name.trim(),
      description: description.trim() || undefined,
      category,
      content: content.trim() || undefined,
      source_type: sourceType,
      tags: tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : undefined,
    })
    setName('')
    setDescription('')
    setCategory('general')
    setSourceType('note')
    setContent('')
    setTags('')
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Add Knowledge Source</h2>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="e.g. Product FAQ" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <input type="text" value={description} onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Brief description" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
                {Object.entries(CATEGORY_CONFIG).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source Type</label>
              <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
                {Object.entries(SOURCE_TYPE_CONFIG).map(([k, v]) => (
                  <option key={k} value={k}>{v.icon} {v.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Paste or type the knowledge content..." />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tags (comma-separated)</label>
            <input type="text" value={tags} onChange={(e) => setTags(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="e.g. pricing, plans, features" />
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg">Cancel</button>
          <button onClick={handleSubmit} disabled={!name.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg disabled:opacity-50">
            Create
          </button>
        </div>
      </div>
    </div>
  )
}

function ManageAccessModal({ isOpen, knowledge, agents, assignedAgents, onClose, onGrant, onRevoke }: {
  isOpen: boolean
  knowledge: Knowledge | null
  agents: AIAgent[]
  assignedAgents: KnowledgeAgentAccess[]
  onClose: () => void
  onGrant: (agentId: string) => void
  onRevoke: (agentId: string) => void
}) {
  if (!isOpen || !knowledge) return null

  const assignedIds = new Set(assignedAgents.map(a => a.agent_id))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Manage Access</h2>
          <p className="text-sm text-gray-500 mt-0.5">{knowledge.name}</p>
        </div>
        <div className="p-6">
          <p className="text-sm font-medium text-gray-700 mb-3">Assign this knowledge to agents:</p>
          <div className="space-y-2">
            {agents.map((agent) => {
              const isAssigned = assignedIds.has(agent.id)
              return (
                <div key={agent.id} className="flex items-center justify-between p-3 rounded-lg border border-gray-200 hover:bg-gray-50">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-sm font-medium text-primary-700">
                      {agent.name.charAt(0)}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-900">{agent.name}</div>
                      <div className="text-xs text-gray-500">{agent.role}</div>
                    </div>
                  </div>
                  <button
                    onClick={() => isAssigned ? onRevoke(agent.id) : onGrant(agent.id)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      isAssigned
                        ? 'bg-green-100 text-green-700 hover:bg-green-200'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}>
                    {isAssigned ? '✓ Assigned' : 'Assign'}
                  </button>
                </div>
              )
            })}
          </div>
          {agents.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-4">No agents available</p>
          )}
        </div>
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg">Done</button>
        </div>
      </div>
    </div>
  )
}

function KnowledgeCard({ knowledge, agents, onView, onManageAccess, onDelete }: {
  knowledge: Knowledge
  agents: AIAgent[]
  onView: () => void
  onManageAccess: () => void
  onDelete: () => void
}) {
  const category = CATEGORY_CONFIG[knowledge.category] || CATEGORY_CONFIG.general
  const sourceType = SOURCE_TYPE_CONFIG[knowledge.source_type] || SOURCE_TYPE_CONFIG.note
  const status = STATUS_CONFIG[knowledge.status] || STATUS_CONFIG.active

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-teal-100 flex items-center justify-center text-lg">
            {sourceType.icon}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{knowledge.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${category.color}`}>
                {category.label}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${status.color}`}>
                {status.label}
              </span>
            </div>
          </div>
        </div>
      </div>

      {knowledge.description && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{knowledge.description}</p>
      )}

      {knowledge.content && (
        <div className="bg-gray-50 rounded-lg p-3 mb-3">
          <p className="text-xs text-gray-500 line-clamp-3">{knowledge.content.substring(0, 200)}...</p>
        </div>
      )}

      <div className="flex items-center gap-2 mb-3 text-xs text-gray-500">
        <span>Chunks: {knowledge.chunk_count || '0'}</span>
        <span>·</span>
        <span>{sourceType.label}</span>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">
          {new Date(knowledge.created_at).toLocaleDateString()}
        </span>
        <div className="flex items-center gap-2">
          <button onClick={onView}
            className="px-3 py-1.5 text-xs font-medium text-primary-600 hover:bg-primary-50 rounded-lg">
            View
          </button>
          <button onClick={onManageAccess}
            className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-lg">
            Access
          </button>
          <button onClick={onDelete}
            className="px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg">
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}

export default function KnowledgePage() {
  const [knowledge, setKnowledge] = useState<Knowledge[]>([])
  const [agents, setAgents] = useState<AIAgent[]>([])
  const [stats, setStats] = useState<KnowledgeStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterCategory, setFilterCategory] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showAccessModal, setShowAccessModal] = useState(false)
  const [selectedKnowledge, setSelectedKnowledge] = useState<Knowledge | null>(null)
  const [viewDetail, setViewDetail] = useState<Knowledge | null>(null)
  const [accessAgents, setAccessAgents] = useState<KnowledgeAgentAccess[]>([])

  useEffect(() => {
    loadData()
  }, [filterCategory, filterType])

  const loadData = async () => {
    try {
      setLoading(true)
      const [knowledgeRes, agentsRes, statsRes] = await Promise.all([
        officeService.getKnowledgeSources({
          category: filterCategory || undefined,
          source_type: filterType || undefined,
          search: searchQuery || undefined,
        }),
        officeService.getAgents(),
        officeService.getKnowledgeStats(),
      ])
      setKnowledge(knowledgeRes.data)
      setAgents(agentsRes.data)
      setStats(statsRes.data)
    } catch (err) {
      setError('Failed to load knowledge base')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (data: { name: string; description?: string; category: string; content?: string; source_type: string; tags?: string[] }) => {
    try {
      await officeService.createKnowledgeSource(data)
      await loadData()
    } catch (err) {
      console.error('Failed to create knowledge source:', err)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this knowledge source?')) return
    try {
      await officeService.deleteKnowledgeSource(id)
      await loadData()
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  const handleManageAccess = async (knowledge: Knowledge) => {
    setSelectedKnowledge(knowledge)
    try {
      const res = await officeService.getKnowledgeAgents(knowledge.id)
      setAccessAgents(res.data)
    } catch {
      setAccessAgents([])
    }
    setShowAccessModal(true)
  }

  const handleGrantAccess = async (agentId: string) => {
    if (!selectedKnowledge) return
    try {
      await officeService.grantKnowledgeAccess(selectedKnowledge.id, agentId)
      const res = await officeService.getKnowledgeAgents(selectedKnowledge.id)
      setAccessAgents(res.data)
    } catch (err) {
      console.error('Failed to grant access:', err)
    }
  }

  const handleRevokeAccess = async (agentId: string) => {
    if (!selectedKnowledge) return
    try {
      await officeService.revokeKnowledgeAccess(selectedKnowledge.id, agentId)
      const res = await officeService.getKnowledgeAgents(selectedKnowledge.id)
      setAccessAgents(res.data)
    } catch (err) {
      console.error('Failed to revoke access:', err)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      await loadData()
      return
    }
    try {
      setLoading(true)
      const [searchRes, agentsRes] = await Promise.all([
        officeService.searchKnowledge(searchQuery),
        officeService.getAgents(),
      ])
      const mapped: Knowledge[] = searchRes.data.map((r) => ({
        id: r.id,
        name: r.name,
        description: null,
        category: r.category,
        content: r.snippet || r.content,
        source_type: 'note' as const,
        status: 'active' as const,
        file_path: null,
        tags: null,
        chunk_count: null,
        embedding_id: null,
        created_by: null,
        created_at: new Date().toISOString(),
        updated_at: null,
      }))
      setKnowledge(mapped)
      setAgents(agentsRes.data)
    } catch (err) {
      console.error('Search failed:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading knowledge base...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-600 mb-2">{error}</p>
          <button onClick={loadData} className="text-sm text-primary-600 hover:text-primary-700">Try again</button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Knowledge Center</h1>
            <p className="text-gray-500 mt-1">Manage company knowledge base for AI agents</p>
          </div>
          <button onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors">
            + Add Knowledge
          </button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <div className="p-3 rounded-xl bg-white border border-gray-200">
            <div className="text-xl font-bold text-gray-900">{stats.total}</div>
            <div className="text-xs text-gray-500">Total Sources</div>
          </div>
          <div className="p-3 rounded-xl bg-white border border-gray-200">
            <div className="text-xl font-bold text-green-600">{stats.active}</div>
            <div className="text-xs text-gray-500">Active</div>
          </div>
          <div className="p-3 rounded-xl bg-white border border-gray-200">
            <div className="text-xl font-bold text-amber-600">{stats.processing}</div>
            <div className="text-xs text-gray-500">Processing</div>
          </div>
          <div className="p-3 rounded-xl bg-white border border-gray-200">
            <div className="text-xl font-bold text-red-600">{stats.error}</div>
            <div className="text-xs text-gray-500">Error</div>
          </div>
          <div className="p-3 rounded-xl bg-white border border-gray-200">
            <div className="text-xl font-bold text-primary-600">{stats.agents_with_access}</div>
            <div className="text-xs text-gray-500">Agents Accessing</div>
          </div>
          <div className="p-3 rounded-xl bg-white border border-gray-200">
            <div className="text-xl font-bold text-gray-900">{Object.keys(stats.by_category).length}</div>
            <div className="text-xs text-gray-500">Categories</div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex-1 min-w-[200px]">
          <div className="relative">
            <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Search knowledge base..." />
            <svg className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
          </div>
        </div>
        <div className="flex gap-2">
          <span className="text-sm text-gray-500 py-1.5">Category:</span>
          {Object.entries(CATEGORY_CONFIG).map(([key, config]) => (
            <button key={key} onClick={() => setFilterCategory(filterCategory === key ? null : key)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                filterCategory === key ? `${config.color}` : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>
              {config.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2 mb-6">
        <span className="text-sm text-gray-500 py-1.5">Type:</span>
        {Object.entries(SOURCE_TYPE_CONFIG).map(([key, config]) => (
          <button key={key} onClick={() => setFilterType(filterType === key ? null : key)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              filterType === key ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}>
            {config.icon} {config.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {knowledge.map((k) => (
          <KnowledgeCard
            key={k.id}
            knowledge={k}
            agents={agents}
            onView={() => setViewDetail(k)}
            onManageAccess={() => handleManageAccess(k)}
            onDelete={() => handleDelete(k.id)}
          />
        ))}
      </div>

      {knowledge.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No knowledge sources found</p>
        </div>
      )}

      <CreateKnowledgeModal isOpen={showCreateModal} onClose={() => setShowCreateModal(false)} onSubmit={handleCreate} />

      <ManageAccessModal
        isOpen={showAccessModal}
        knowledge={selectedKnowledge}
        agents={agents}
        assignedAgents={accessAgents}
        onClose={() => setShowAccessModal(false)}
        onGrant={handleGrantAccess}
        onRevoke={handleRevokeAccess}
      />

      {viewDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">{viewDetail.name}</h2>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${CATEGORY_CONFIG[viewDetail.category]?.color || ''}`}>
                    {CATEGORY_CONFIG[viewDetail.category]?.label || viewDetail.category}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_CONFIG[viewDetail.status]?.color || ''}`}>
                    {STATUS_CONFIG[viewDetail.status]?.label || viewDetail.status}
                  </span>
                </div>
              </div>
              <button onClick={() => setViewDetail(null)} className="text-gray-400 hover:text-gray-600">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6">
              {viewDetail.description && (
                <p className="text-sm text-gray-600 mb-4">{viewDetail.description}</p>
              )}
              {viewDetail.content && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Content</h3>
                  <div className="text-sm text-gray-600 whitespace-pre-wrap">{viewDetail.content}</div>
                </div>
              )}
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <button onClick={() => setViewDetail(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
