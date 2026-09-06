import { useState, useEffect } from 'react'
import type { Permission, AgentPermission } from '../types'
import { officeService } from '../services/office'

const PERMISSION_CATEGORIES: Record<string, { label: string; icon: string; color: string }> = {
  email: { label: 'Email', icon: '✉', color: 'bg-red-100 text-red-700' },
  support: { label: 'Support', icon: '🎧', color: 'bg-orange-100 text-orange-700' },
  crm: { label: 'CRM', icon: '👥', color: 'bg-amber-100 text-amber-700' },
  sales: { label: 'Sales', icon: '💰', color: 'bg-green-100 text-green-700' },
  finance: { label: 'Finance', icon: '💳', color: 'bg-emerald-100 text-emerald-700' },
  knowledge: { label: 'Knowledge', icon: '📚', color: 'bg-teal-100 text-teal-700' },
  content: { label: 'Content', icon: '📝', color: 'bg-purple-100 text-purple-700' },
  social: { label: 'Social', icon: '🌐', color: 'bg-pink-100 text-pink-700' },
  research: { label: 'Research', icon: '🔍', color: 'bg-cyan-100 text-cyan-700' },
  analytics: { label: 'Analytics', icon: '📊', color: 'bg-indigo-100 text-indigo-700' },
  data: { label: 'Data', icon: '🗄', color: 'bg-violet-100 text-violet-700' },
  calendar: { label: 'Calendar', icon: '📅', color: 'bg-blue-100 text-blue-700' },
  general: { label: 'General', icon: '⚙', color: 'bg-gray-100 text-gray-700' },
}

const RISK_LEVELS: Record<string, { label: string; color: string }> = {
  low: { label: 'Low', color: 'bg-green-100 text-green-700' },
  medium: { label: 'Medium', color: 'bg-amber-100 text-amber-700' },
  high: { label: 'High', color: 'bg-red-100 text-red-700' },
  critical: { label: 'Critical', color: 'bg-red-200 text-red-800' },
}

const ACCESS_LEVELS: Record<string, { label: string; color: string; icon: string }> = {
  allowed: { label: 'Allowed', color: 'bg-green-100 text-green-700', icon: '✓' },
  approval_required: { label: 'Approval Required', color: 'bg-amber-100 text-amber-700', icon: '⚠' },
  denied: { label: 'Denied', color: 'bg-red-100 text-red-700', icon: '✗' },
}

function PermissionCard({ permission, accessLevel, onToggle }: {
  permission: Permission
  accessLevel?: string
  onToggle: (permissionId: string, newLevel: string) => void
}) {
  const category = PERMISSION_CATEGORIES[permission.category] || PERMISSION_CATEGORIES.general
  const risk = RISK_LEVELS[permission.risk_level] || RISK_LEVELS.low
  const currentLevel = accessLevel || 'allowed'
  const levelInfo = ACCESS_LEVELS[currentLevel] || ACCESS_LEVELS.allowed

  const cycleLevel = () => {
    const levels = ['allowed', 'approval_required', 'denied']
    const currentIndex = levels.indexOf(currentLevel)
    const nextIndex = (currentIndex + 1) % levels.length
    onToggle(permission.id, levels[nextIndex])
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg ${category.color}`}>
            {category.icon}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{permission.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${category.color}`}>
                {category.label}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${risk.color}`}>
                {risk.label} Risk
              </span>
            </div>
          </div>
        </div>
        <button
          onClick={cycleLevel}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${levelInfo.color}`}
        >
          {levelInfo.icon} {levelInfo.label}
        </button>
      </div>

      {permission.description && (
        <p className="text-sm text-gray-600 mb-3">{permission.description}</p>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">
          {permission.default_approval_required ? 'Default: Approval Required' : 'Default: Allowed'}
        </span>
      </div>
    </div>
  )
}

export default function PermissionsPage() {
  const [permissions, setPermissions] = useState<Permission[]>([])
  const [agentPermissions, setAgentPermissions] = useState<AgentPermission[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAgentId] = useState<string | null>(null)

  useEffect(() => {
    loadPermissions()
  }, [])

  const loadPermissions = async () => {
    try {
      setLoading(true)
      const res = await officeService.getPermissions()
      setPermissions(res.data ?? [])
    } catch (err) {
      setError('Failed to load permissions')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const loadAgentPermissions = async (agentId: string) => {
    try {
      const res = await officeService.getAgentPermissions(agentId)
      setAgentPermissions(res.data ?? [])
    } catch (err) {
      console.error('Failed to load agent permissions:', err)
    }
  }

  const togglePermission = async (permissionId: string, newLevel: string) => {
    if (!selectedAgentId) return

    try {
      const existing = agentPermissions.find(ap => ap.permission_id === permissionId)
      if (existing) {
        await officeService.updateAgentPermission(selectedAgentId, permissionId, { access_level: newLevel })
      } else {
        await officeService.setAgentPermission(selectedAgentId, permissionId, newLevel)
      }
      await loadAgentPermissions(selectedAgentId)
    } catch (err) {
      console.error('Failed to toggle permission:', err)
    }
  }

  const filteredPermissions = permissions.filter((perm) => {
    if (selectedCategory && perm.category !== selectedCategory) return false
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        perm.name.toLowerCase().includes(query) ||
        perm.description?.toLowerCase().includes(query)
      )
    }
    return true
  })

  const categories = Array.from(new Set(permissions.map(p => p.category)))

  const getAccessLevel = (permissionId: string): string | undefined => {
    const agentPerm = agentPermissions.find(ap => ap.permission_id === permissionId)
    return agentPerm?.access_level
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading permissions...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-600 mb-2">{error}</p>
          <button onClick={loadPermissions} className="text-sm text-primary-600 hover:text-primary-700">
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
            <h1 className="text-2xl font-bold text-gray-900">Permission Registry</h1>
            <p className="text-gray-500 mt-1">Manage permissions for AI agents</p>
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>{permissions.length} permissions</span>
            <span className="w-1 h-1 bg-gray-300 rounded-full" />
            <span>{agentPermissions.length} assigned</span>
          </div>
        </div>
      </div>

      <div className="mb-6">
        <div className="flex items-center gap-4">
          <div className="flex-1 max-w-md">
            <input
              type="text"
              placeholder="Search permissions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                !selectedCategory
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              All
            </button>
            {categories.map((cat) => {
              const catInfo = PERMISSION_CATEGORIES[cat] || PERMISSION_CATEGORIES.general
              return (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                    selectedCategory === cat
                      ? 'bg-primary-100 text-primary-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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
        {filteredPermissions.map((permission) => (
          <PermissionCard
            key={permission.id}
            permission={permission}
            accessLevel={getAccessLevel(permission.id)}
            onToggle={togglePermission}
          />
        ))}
      </div>

      {filteredPermissions.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No permissions found</p>
        </div>
      )}
    </div>
  )
}
