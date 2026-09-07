import { useState, useEffect } from 'react'
import type { AgentTool, ToolAction, ToolWithActions } from '../types'
import { officeService } from '../services/office'

const TOOL_CATEGORIES: Record<string, { label: string; icon: string; color: string }> = {
  email: { label: 'Email', icon: 'âœ‰', color: 'bg-red-500/15 text-red-300' },
  communication: { label: 'Communication', icon: 'ðŸ’¬', color: 'bg-blue-500/15 text-blue-300' },
  crm: { label: 'CRM', icon: 'ðŸ‘¥', color: 'bg-amber-500/15 text-amber-300' },
  sales: { label: 'Sales', icon: 'ðŸ’°', color: 'bg-green-500/15 text-green-300' },
  content: { label: 'Content', icon: 'ðŸ“', color: 'bg-purple-500/15 text-purple-300' },
  analytics: { label: 'Analytics', icon: 'ðŸ“Š', color: 'bg-indigo-500/15 text-indigo-300' },
  productivity: { label: 'Productivity', icon: 'âš¡', color: 'bg-yellow-500/15 text-yellow-300' },
  knowledge: { label: 'Knowledge', icon: 'ðŸ“š', color: 'bg-teal-500/15 text-teal-300' },
  support: { label: 'Support', icon: 'ðŸŽ§', color: 'bg-orange-500/15 text-orange-300' },
  research: { label: 'Research', icon: 'ðŸ”', color: 'bg-cyan-500/15 text-cyan-300' },
  social: { label: 'Social', icon: 'ðŸŒ', color: 'bg-pink-500/15 text-pink-300' },
  calendar: { label: 'Calendar', icon: 'ðŸ“…', color: 'bg-blue-500/15 text-blue-300' },
  finance: { label: 'Finance', icon: 'ðŸ’³', color: 'bg-emerald-500/15 text-emerald-300' },
  data: { label: 'Data', icon: 'ðŸ—„', color: 'bg-violet-500/15 text-violet-300' },
  general: { label: 'General', icon: 'âš™', color: 'bg-white/10 text-white/80' },
}

const RISK_LEVELS: Record<string, { label: string; color: string }> = {
  low: { label: 'Low', color: 'bg-green-500/15 text-green-300' },
  medium: { label: 'Medium', color: 'bg-amber-500/15 text-amber-300' },
  high: { label: 'High', color: 'bg-red-500/15 text-red-300' },
  critical: { label: 'Critical', color: 'bg-red-500/25 text-red-300' },
}

function ActionRow({ action }: { action: ToolAction }) {
  const risk = RISK_LEVELS[action.risk_level] || RISK_LEVELS.low

  return (
    <div className="flex items-center justify-between py-2 px-3 bg-white/[0.04] rounded-lg">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-white">{action.display_name}</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${risk.color}`}>
          {risk.label}
        </span>
        {action.requires_approval && (
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-orange-500/15 text-orange-300">
            Approval Required
          </span>
        )}
      </div>
      <p className="text-xs text-white/50 max-w-[200px] truncate">{action.description}</p>
    </div>
  )
}

function ToolCard({ tool, onToggle, isSelected }: {
  tool: AgentTool
  onToggle: (toolId: string) => void
  isSelected: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const [toolDetails, setToolDetails] = useState<ToolWithActions | null>(null)
  const [loading, setLoading] = useState(false)

  const category = TOOL_CATEGORIES[tool.category] || TOOL_CATEGORIES.general
  const risk = RISK_LEVELS[tool.risk_level] || RISK_LEVELS.low

  const handleExpand = async () => {
    if (expanded) {
      setExpanded(false)
      return
    }

    if (!toolDetails) {
      setLoading(true)
      try {
        const res = await officeService.getToolWithActions(tool.id)
        setToolDetails(res.data ?? null)
      } catch (err) {
        console.error('Failed to load tool details:', err)
      } finally {
        setLoading(false)
      }
    }
    setExpanded(true)
  }

  return (
    <div className={`bg-white/[0.03] rounded-xl border transition-all ${
      isSelected ? 'border-indigo-500/40 ring-2 ring-indigo-500/20' : 'border-white/10'
    }`}>
      <div className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg ${category.color}`}>
              {category.icon}
            </div>
            <div>
              <h3 className="font-semibold text-white">{tool.display_name}</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${category.color}`}>
                  {category.label}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${risk.color}`}>
                  {risk.label} Risk
                </span>
                {tool.requires_approval && (
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-orange-500/15 text-orange-300">
                    Approval
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={() => onToggle(tool.id)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              isSelected ? 'bg-indigo-600' : 'bg-white/10'
            }`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              isSelected ? 'translate-x-6' : 'translate-x-1'
            }`} />
          </button>
        </div>

        <p className="text-sm text-white/70 mb-3">{tool.description}</p>

        {tool.integration_id && (
          <div className="flex items-center gap-1 text-xs text-white/50 mb-3">
            <span className="w-1.5 h-1.5 bg-blue-500 rounded-full" />
            Requires integration connection
          </div>
        )}

        <div className="flex items-center justify-between pt-3 border-t border-white/6">
          <span className="text-xs text-white/40">v{tool.version}</span>
          <button
            onClick={handleExpand}
            className="text-sm text-indigo-400 hover:text-indigo-300 font-medium"
          >
            {loading ? 'Loading...' : expanded ? 'Hide Actions' : 'View Actions'}
          </button>
        </div>
      </div>

      {expanded && toolDetails && (
        <div className="px-5 pb-5 border-t border-white/6">
          <div className="mt-4">
            <h4 className="text-sm font-medium text-white/80 mb-3">Available Actions</h4>
            <div className="space-y-2">
              {toolDetails.actions.map((action) => (
                <ActionRow key={action.id} action={action} />
              ))}
            </div>
          </div>

          {toolDetails.permissions.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium text-white/80 mb-2">Required Permissions</h4>
              <div className="flex flex-wrap gap-1">
                {toolDetails.permissions.map((tp) => (
                  <span key={tp.id} className="px-2 py-1 bg-white/10 text-white/70 rounded text-xs">
                    {tp.permission_id}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ToolsPage() {
  const [tools, setTools] = useState<AgentTool[]>([])
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadTools()
  }, [])

  const loadTools = async () => {
    try {
      setLoading(true)
      const res = await officeService.getTools()
      setTools(res.data ?? [])
    } catch (err) {
      setError('Failed to load tools')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) => {
      const next = new Set(prev)
      if (next.has(toolId)) {
        next.delete(toolId)
      } else {
        next.add(toolId)
      }
      return next
    })
  }

  const filteredTools = tools.filter((tool) => {
    if (selectedCategory && tool.category !== selectedCategory) return false
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        tool.display_name.toLowerCase().includes(query) ||
        tool.description?.toLowerCase().includes(query) ||
        tool.name.toLowerCase().includes(query)
      )
    }
    return true
  })

  const categories = Array.from(new Set(tools.map((t) => t.category)))

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-white/10 border-t-indigo-400 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-white/50">Loading tools...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-400 mb-2">{error}</p>
          <button onClick={loadTools} className="text-sm text-indigo-400 hover:text-indigo-300">
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
            <h1 className="text-2xl font-bold text-white">Tool Registry</h1>
            <p className="text-white/50 mt-1">Manage available tools for AI agents</p>
          </div>
          <div className="flex items-center gap-4 text-sm text-white/50">
            <span>{tools.length} tools</span>
            <span className="w-1 h-1 bg-white/20 rounded-full" />
            <span>{selectedTools.size} selected</span>
          </div>
        </div>
      </div>

      <div className="mb-6">
        <div className="flex items-center gap-4">
          <div className="flex-1 max-w-md">
            <input
              type="text"
              placeholder="Search tools..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-white/15 rounded-lg focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                !selectedCategory
                  ? 'bg-indigo-500/20 text-indigo-200'
                  : 'bg-white/10 text-white/70 hover:bg-white/15'
              }`}
            >
              All
            </button>
            {categories.map((cat) => {
              const catInfo = TOOL_CATEGORIES[cat] || TOOL_CATEGORIES.general
              return (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                    selectedCategory === cat
                      ? 'bg-indigo-500/20 text-indigo-200'
                      : 'bg-white/10 text-white/70 hover:bg-white/15'
                  }`}
                >
                  {catInfo.icon} {catInfo.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredTools.map((tool) => (
          <ToolCard
            key={tool.id}
            tool={tool}
            onToggle={toggleTool}
            isSelected={selectedTools.has(tool.id)}
          />
        ))}
      </div>

      {filteredTools.length === 0 && (
        <div className="text-center py-12">
          <p className="text-white/50">No tools found</p>
        </div>
      )}
    </div>
  )
}
