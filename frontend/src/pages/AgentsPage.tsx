import { useState, useEffect, useCallback } from 'react'
import type { AIAgent, AgentTemplate, AgentTool, Permission, Integration, OfficeRoom, HireAgentRequest } from '../types'
import { officeService } from '../services/office'

const LIFECYCLE_COLORS: Record<string, string> = {
  draft: 'bg-white/10 text-white/70',
  active: 'bg-green-500/15 text-green-300',
  paused: 'bg-amber-500/15 text-amber-300',
  inactive: 'bg-white/10 text-white/50',
  error: 'bg-red-500/15 text-red-300',
  disabled: 'bg-red-500/15 text-red-500',
  archived: 'bg-white/10 text-white/40',
}

const LIFECYCLE_DOT: Record<string, string> = {
  draft: 'bg-white/30',
  active: 'bg-green-500',
  paused: 'bg-amber-500',
  inactive: 'bg-white/30',
  error: 'bg-red-500',
  disabled: 'bg-red-400',
  archived: 'bg-white/20',
}

const TEMPLATE_ICONS: Record<string, string> = {
  email_support: 'M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75',
  content_writer: 'M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10',
  social_media: 'M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418',
  research: 'M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5',
  sales: 'M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z',
  analyst: 'M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605',
  executive_assistant: 'M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0M12 12.75h.008v.008H12v-.008z',
  customer_support: 'M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155',
}

const INTEGRATION_ICONS: Record<string, string> = {
  gmail: 'M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75',
  slack: 'M13.5 21v-7.5a.75.75 0 01.75-.75h3a.75.75 0 01.75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349m-16.5 11.65V9.35m0 0a3.001 3.001 0 003.75-.615A2.993 2.993 0 009.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 002.25 1.016c.896 0 1.7-.393 2.25-1.016a3.001 3.001 0 003.75.614m-16.5 0a3.004 3.004 0 01-.621-4.72l1.189-1.19A1.5 1.5 0 0119.5 3h1.15a1.5 1.5 0 011.5 1.5v3.644a1.5 1.5 0 01-.44 1.06l-1.19 1.19a3 3 0 01-3.75-.614',
  discord: 'M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418',
}

type ViewMode = 'agents' | 'templates'

interface WizardStep {
  id: string
  title: string
  description: string
}

const WIZARD_STEPS: WizardStep[] = [
  { id: 'template', title: 'Select Template', description: 'Choose an agent template' },
  { id: 'details', title: 'Name & Describe', description: 'Customize your agent' },
  { id: 'tools', title: 'Select Tools', description: 'Pick available tools' },
  { id: 'integrations', title: 'Connect Integrations', description: 'Link external services' },
  { id: 'permissions', title: 'Set Permissions', description: 'Configure access levels' },
  { id: 'room', title: 'Assign Room', description: 'Place in your office' },
  { id: 'review', title: 'Review & Hire', description: 'Confirm your choices' },
]

function AgentsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('agents')
  const [agents, setAgents] = useState<AIAgent[]>([])
  const [templates, setTemplates] = useState<AgentTemplate[]>([])
  const [rooms, setRooms] = useState<OfficeRoom[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')

  const [showWizard, setShowWizard] = useState(false)
  const [wizardStep, setWizardStep] = useState(0)
  const [selectedTemplate, setSelectedTemplate] = useState<AgentTemplate | null>(null)
  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([])
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>([])
  const [selectedIntegrationIds, setSelectedIntegrationIds] = useState<string[]>([])
  const [selectedRoomId, setSelectedRoomId] = useState('')
  const [autoCreateRoom, setAutoCreateRoom] = useState(true)
  const [availableTools, setAvailableTools] = useState<AgentTool[]>([])
  const [availablePermissions, setAvailablePermissions] = useState<Permission[]>([])
  const [availableIntegrations, setAvailableIntegrations] = useState<Integration[]>([])
  const [isHiring, setIsHiring] = useState(false)

  const [showConfirmHire, setShowConfirmHire] = useState(false)
  const [deletingAgent, setDeletingAgent] = useState<AIAgent | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    const [agentsResult, templatesResult, roomsResult] = await Promise.all([
      officeService.getAgents(),
      officeService.getHiringTemplates(),
      officeService.getRooms(),
    ])
    if (agentsResult.success && agentsResult.data) setAgents(agentsResult.data)
    if (templatesResult.success && templatesResult.data) setTemplates(templatesResult.data)
    if (roomsResult.success && roomsResult.data) setRooms(roomsResult.data)
    if (!agentsResult.success) setError(agentsResult.error ?? 'Failed to load agents')
    setIsLoading(false)
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  const startHireWizard = async (template: AgentTemplate) => {
    setSelectedTemplate(template)
    setAgentName(template.name)
    setAgentDescription(template.description ?? '')
    setSelectedToolIds([])
    setSelectedPermissionIds([])
    setSelectedIntegrationIds([])
    setSelectedRoomId('')
    setAutoCreateRoom(true)
    setWizardStep(0)
    setShowWizard(true)

    const [toolsResult, permsResult, integrationsResult] = await Promise.all([
      officeService.getTemplateTools(template.id),
      officeService.getTemplatePermissions(template.id),
      officeService.getTemplateIntegrations(template.id),
    ])
    if (toolsResult.success && toolsResult.data) {
      setAvailableTools(toolsResult.data)
      setSelectedToolIds(toolsResult.data.map((t) => t.id))
    }
    if (permsResult.success && permsResult.data) {
      setAvailablePermissions(permsResult.data)
      setSelectedPermissionIds(permsResult.data.map((p) => p.id))
    }
    if (integrationsResult.success && integrationsResult.data) {
      setAvailableIntegrations(integrationsResult.data)
      setSelectedIntegrationIds(integrationsResult.data.map((i) => i.id))
    }
  }

  const handleHire = async () => {
    if (!selectedTemplate) return
    setIsHiring(true)
    try {
      const data: HireAgentRequest = {
        template_id: selectedTemplate.id,
        name: agentName.trim(),
        description: agentDescription.trim() || undefined,
        room_id: autoCreateRoom ? undefined : (selectedRoomId || undefined),
        tool_ids: selectedToolIds.length > 0 ? selectedToolIds : undefined,
        permission_ids: selectedPermissionIds.length > 0 ? selectedPermissionIds : undefined,
        integration_ids: selectedIntegrationIds.length > 0 ? selectedIntegrationIds : undefined,
        auto_create_room: autoCreateRoom,
      }
      const result = await officeService.hireAgent(data)
      if (!result.success) throw new Error(result.error ?? 'Failed to hire agent')
      setShowWizard(false)
      setShowConfirmHire(false)
      await fetchData()
      setViewMode('agents')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to hire agent')
    } finally {
      setIsHiring(false)
    }
  }

  const handleDelete = async () => {
    if (!deletingAgent) return
    setIsDeleting(true)
    try {
      const result = await officeService.deleteAgent(deletingAgent.id)
      if (!result.success) throw new Error(result.error ?? 'Failed to delete agent')
      setDeletingAgent(null)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete agent')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleLifecycle = async (agentId: string, action: 'pause' | 'resume' | 'disable' | 'archive' | 'restart', reason?: string) => {
    const result = await officeService.updateAgentLifecycle(agentId, action, reason)
    if (!result.success) {
      setError(result.error ?? 'Failed to update agent')
      return
    }
    await fetchData()
  }

  const toggleTool = (toolId: string) => {
    setSelectedToolIds((prev) =>
      prev.includes(toolId) ? prev.filter((id) => id !== toolId) : [...prev, toolId]
    )
  }

  const togglePermission = (permId: string) => {
    setSelectedPermissionIds((prev) =>
      prev.includes(permId) ? prev.filter((id) => id !== permId) : [...prev, permId]
    )
  }

  const toggleIntegration = (intId: string) => {
    setSelectedIntegrationIds((prev) =>
      prev.includes(intId) ? prev.filter((id) => id !== intId) : [...prev, intId]
    )
  }

  const getRoomName = (roomId: string | null) => {
    if (!roomId) return null
    return rooms.find((r) => r.id === roomId)?.name ?? null
  }

  const nextStep = () => setWizardStep((s) => Math.min(s + 1, WIZARD_STEPS.length - 1))
  const prevStep = () => setWizardStep((s) => Math.max(s - 1, 0))

  const filteredAgents = agents.filter((agent) => {
    const matchesSearch = !searchQuery ||
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.role.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = filterStatus === 'all' || agent.lifecycle_status === filterStatus
    return matchesSearch && matchesStatus
  })

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="h-8 w-48 bg-white/10 rounded animate-pulse" />
          <div className="h-4 w-64 bg-white/10 rounded animate-pulse mt-2" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-48 bg-white/10 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {error && (
        <div className="mb-4 bg-red-500/10 border border-red-500/25 text-red-300 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-300">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      <div className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Agents</h1>
          <p className="mt-1 text-sm text-white/50">Manage your AI workforce and hire new agents from templates.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-white/5 border border-white/10 rounded-lg p-1">
            <button
              type="button"
              onClick={() => setViewMode('agents')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === 'agents' ? 'bg-white/10 text-white' : 'text-white/50 hover:text-white/80'
              }`}
            >
              My Agents ({agents.length})
            </button>
            <button
              type="button"
              onClick={() => setViewMode('templates')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === 'templates' ? 'bg-white/10 text-white' : 'text-white/50 hover:text-white/80'
              }`}
            >
              Templates ({templates.length})
            </button>
          </div>
        </div>
      </div>

      {viewMode === 'agents' && (
        <div className="mb-4 flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/40" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search agents..."
              className="w-full pl-9 pr-3 py-2 text-sm border border-white/15 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50"
            />
          </div>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 text-sm border border-white/15 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50 bg-white/5"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="inactive">Inactive</option>
            <option value="disabled">Disabled</option>
          </select>
        </div>
      )}

      {viewMode === 'agents' ? (
        filteredAgents.length === 0 ? (
          <div className="bg-white/[0.03] rounded-xl border border-white/10 p-12 text-center">
            <svg className="mx-auto h-12 w-12 text-white/25" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
            </svg>
            <h3 className="mt-3 text-sm font-medium text-white">
              {agents.length === 0 ? 'No agents yet' : 'No matching agents'}
            </h3>
            <p className="mt-1 text-sm text-white/50">
              {agents.length === 0 ? 'Switch to Templates to hire your first AI agent.' : 'Try adjusting your search or filter.'}
            </p>
            {agents.length === 0 && (
              <button
                type="button"
                onClick={() => setViewMode('templates')}
                className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 transition-colors"
              >
                Browse Templates
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredAgents.map((agent) => (
              <div key={agent.id} className="bg-white/[0.03] rounded-xl border border-white/10 p-5 hover:bg-white/[0.05] hover:border-white/15 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center justify-center h-10 w-10 rounded-full bg-indigo-500/20 text-indigo-200 text-sm font-medium shrink-0">
                      {agent.name.charAt(0)}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate">{agent.name}</p>
                      <p className="text-xs text-white/50 truncate">{agent.role}</p>
                    </div>
                  </div>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${LIFECYCLE_COLORS[agent.lifecycle_status] ?? LIFECYCLE_COLORS.draft}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${LIFECYCLE_DOT[agent.lifecycle_status] ?? LIFECYCLE_DOT.draft}`} />
                    {agent.lifecycle_status}
                  </span>
                </div>
                {agent.description && (
                  <p className="text-xs text-white/50 mb-3 line-clamp-2">{agent.description}</p>
                )}
                {agent.lifecycle_status === 'error' && agent.last_error && (
                  <div className="bg-red-500/10 border border-red-500/25 rounded-lg p-2 mb-3">
                    <p className="text-xs text-red-300 line-clamp-2">{agent.last_error}</p>
                  </div>
                )}
                {agent.lifecycle_status === 'disabled' && agent.disabled_reason && (
                  <div className="bg-white/[0.04] border border-white/10 rounded-lg p-2 mb-3">
                    <p className="text-xs text-white/70 line-clamp-2">{agent.disabled_reason}</p>
                  </div>
                )}
                <div className="flex items-center gap-2 text-xs text-white/50 mb-4">
                  {getRoomName(agent.room_id) && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-white/10 rounded-md">
                      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3H21" />
                      </svg>
                      {getRoomName(agent.room_id)}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  {agent.lifecycle_status === 'active' && (
                    <button
                      type="button"
                      onClick={() => handleLifecycle(agent.id, 'pause')}
                      className="flex-1 px-2 py-1.5 text-xs font-medium text-amber-300 bg-amber-500/10 rounded-lg hover:bg-amber-500/20 transition-colors"
                    >
                      Pause
                    </button>
                  )}
                  {agent.lifecycle_status === 'paused' && (
                    <button
                      type="button"
                      onClick={() => handleLifecycle(agent.id, 'resume')}
                      className="flex-1 px-2 py-1.5 text-xs font-medium text-green-300 bg-green-500/10 rounded-lg hover:bg-green-500/20 transition-colors"
                    >
                      Resume
                    </button>
                  )}
                  {agent.lifecycle_status === 'error' && (
                    <button
                      type="button"
                      onClick={() => handleLifecycle(agent.id, 'restart')}
                      className="flex-1 px-2 py-1.5 text-xs font-medium text-blue-300 bg-blue-500/10 rounded-lg hover:bg-blue-500/20 transition-colors"
                    >
                      Restart
                    </button>
                  )}
                  {(agent.lifecycle_status === 'draft' || agent.lifecycle_status === 'inactive') && (
                    <button
                      type="button"
                      onClick={() => handleLifecycle(agent.id, 'resume')}
                      className="flex-1 px-2 py-1.5 text-xs font-medium text-green-300 bg-green-500/10 rounded-lg hover:bg-green-500/20 transition-colors"
                    >
                      Activate
                    </button>
                  )}
                  {agent.lifecycle_status !== 'disabled' && agent.lifecycle_status !== 'archived' && agent.lifecycle_status !== 'error' && (
                    <button
                      type="button"
                      onClick={() => handleLifecycle(agent.id, 'disable')}
                      className="flex-1 px-2 py-1.5 text-xs font-medium text-red-300 bg-red-500/10 rounded-lg hover:bg-red-500/20 transition-colors"
                    >
                      Disable
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setDeletingAgent(agent)}
                    className="px-2 py-1.5 text-xs font-medium text-red-500 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors"
                    title="Fire agent"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.filter((t) => t.is_active).map((template) => (
            <div key={template.id} className="bg-white/[0.03] rounded-xl border border-white/10 p-5 hover:bg-white/[0.05] hover:border-white/15 transition-colors flex flex-col">
              <div className="flex items-start gap-3 mb-3">
                <span className="flex items-center justify-center h-10 w-10 rounded-lg bg-indigo-500/10 text-indigo-400 shrink-0">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d={TEMPLATE_ICONS[template.role] ?? TEMPLATE_ICONS.email_support} />
                  </svg>
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white">{template.name}</p>
                  <p className="text-xs text-white/50 capitalize">{template.role.replace(/_/g, ' ')}</p>
                </div>
              </div>
              {template.description && (
                <p className="text-xs text-white/50 mb-4 line-clamp-3 flex-1">{template.description}</p>
              )}
              <div className="flex items-center gap-4 text-xs text-white/50 mb-4">
                {template.default_tools && (
                  <span className="flex items-center gap-1">
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.384 3.18A1.125 1.125 0 014.5 17.3V5.7a1.125 1.125 0 011.536-1.05l5.384 3.18a1.125 1.125 0 010 1.9z" />
                    </svg>
                    {template.default_tools.length} tools
                  </span>
                )}
                {template.default_permissions && (
                  <span className="flex items-center gap-1">
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                    </svg>
                    {template.default_permissions.length} perms
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => startHireWizard(template)}
                className="w-full px-3 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 transition-colors"
              >
                Hire Agent
              </button>
            </div>
          ))}
        </div>
      )}

      {showWizard && selectedTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => !isHiring && setShowWizard(false)} />
          <div className="relative bg-[#0d0d1a] border border-white/10 rounded-xl shadow-2xl shadow-black/60 w-full max-w-2xl mx-4 overflow-hidden max-h-[90vh] flex flex-col">
            <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between shrink-0">
              <div>
                <h2 className="text-base font-semibold text-white">Hire Agent</h2>
                <p className="text-xs text-white/50 mt-0.5">from {selectedTemplate.name} template</p>
              </div>
              <button
                type="button"
                onClick={() => setShowWizard(false)}
                disabled={isHiring}
                className="p-1 rounded-md text-white/40 hover:text-white/70 hover:bg-white/10 disabled:opacity-50"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="px-5 py-3 border-b border-white/6 shrink-0">
              <div className="flex items-center gap-2">
                {WIZARD_STEPS.map((step, i) => (
                  <div key={step.id} className="flex items-center gap-2 flex-1">
                    <div className={`flex items-center justify-center h-6 w-6 rounded-full text-xs font-medium shrink-0 ${
                      i <= wizardStep ? 'bg-indigo-600 text-white' : 'bg-white/10 text-white/40'
                    }`}>
                      {i < wizardStep ? (
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      ) : (
                        i + 1
                      )}
                    </div>
                    {i < WIZARD_STEPS.length - 1 && (
                      <div className={`h-0.5 flex-1 rounded ${i < wizardStep ? 'bg-indigo-600' : 'bg-white/10'}`} />
                    )}
                  </div>
                ))}
              </div>
              <p className="text-xs text-white/50 mt-2">{WIZARD_STEPS[wizardStep].description}</p>
            </div>

            <div className="px-5 py-4 overflow-y-auto flex-1">
              {wizardStep === 0 && (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-white/80">Selected Template</p>
                  <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-lg p-4 flex items-center gap-3">
                    <span className="flex items-center justify-center h-10 w-10 rounded-lg bg-indigo-500/20 text-indigo-400 shrink-0">
                      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d={TEMPLATE_ICONS[selectedTemplate.role] ?? TEMPLATE_ICONS.email_support} />
                      </svg>
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-white">{selectedTemplate.name}</p>
                      <p className="text-xs text-white/50">{selectedTemplate.description}</p>
                    </div>
                  </div>
                  <p className="text-xs text-white/50">Switch to Templates tab to choose a different template.</p>
                </div>
              )}

              {wizardStep === 1 && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-1">Agent Name</label>
                    <input
                      type="text"
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-white/15 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50"
                      placeholder="e.g. Support Bot"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-1">Description</label>
                    <textarea
                      value={agentDescription}
                      onChange={(e) => setAgentDescription(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 text-sm border border-white/15 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50 resize-none"
                      placeholder="What does this agent do?"
                    />
                  </div>
                </div>
              )}

              {wizardStep === 2 && (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-white/80">Select tools this agent can use</p>
                  {availableTools.length === 0 ? (
                    <p className="text-xs text-white/50">No tools available for this template.</p>
                  ) : (
                    <div className="space-y-2">
                      {availableTools.map((tool) => (
                        <label
                          key={tool.id}
                          className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                            selectedToolIds.includes(tool.id)
                              ? 'border-indigo-500/40 bg-indigo-500/10'
                              : 'border-white/10 hover:bg-white/10'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedToolIds.includes(tool.id)}
                            onChange={() => toggleTool(tool.id)}
                            className="h-4 w-4 rounded border-white/15 text-indigo-400 focus:ring-indigo-500/40"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white">{tool.display_name}</p>
                            {tool.description && (
                              <p className="text-xs text-white/50 truncate">{tool.description}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className={`text-xs px-1.5 py-0.5 rounded ${
                              tool.risk_level === 'high' ? 'bg-red-500/15 text-red-300' :
                              tool.risk_level === 'medium' ? 'bg-amber-500/15 text-amber-300' :
                              'bg-green-500/15 text-green-300'
                            }`}>
                              {tool.risk_level}
                            </span>
                            {tool.requires_approval && (
                              <span className="text-xs px-1.5 py-0.5 rounded bg-white/10 text-white/70">approval</span>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {wizardStep === 3 && (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-white/80">Connect integrations for this agent</p>
                  {availableIntegrations.length === 0 ? (
                    <p className="text-xs text-white/50">No integrations available for this template.</p>
                  ) : (
                    <div className="space-y-2">
                      {availableIntegrations.map((integration) => (
                        <label
                          key={integration.id}
                          className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                            selectedIntegrationIds.includes(integration.id)
                              ? 'border-indigo-500/40 bg-indigo-500/10'
                              : 'border-white/10 hover:bg-white/10'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedIntegrationIds.includes(integration.id)}
                            onChange={() => toggleIntegration(integration.id)}
                            className="h-4 w-4 rounded border-white/15 text-indigo-400 focus:ring-indigo-500/40"
                          />
                          <span className="flex items-center justify-center h-8 w-8 rounded-lg bg-white/10 text-white/70 shrink-0">
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" d={INTEGRATION_ICONS[integration.name] ?? INTEGRATION_ICONS.gmail} />
                            </svg>
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white">{integration.display_name}</p>
                            {integration.description && (
                              <p className="text-xs text-white/50 truncate">{integration.description}</p>
                            )}
                          </div>
                          <span className="text-xs px-1.5 py-0.5 rounded bg-white/10 text-white/70 shrink-0">
                            {integration.auth_type}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {wizardStep === 4 && (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-white/80">Set permissions for this agent</p>
                  {availablePermissions.length === 0 ? (
                    <p className="text-xs text-white/50">No permissions available for this template.</p>
                  ) : (
                    <div className="space-y-2">
                      {availablePermissions.map((perm) => (
                        <label
                          key={perm.id}
                          className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                            selectedPermissionIds.includes(perm.id)
                              ? 'border-indigo-500/40 bg-indigo-500/10'
                              : 'border-white/10 hover:bg-white/10'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedPermissionIds.includes(perm.id)}
                            onChange={() => togglePermission(perm.id)}
                            className="h-4 w-4 rounded border-white/15 text-indigo-400 focus:ring-indigo-500/40"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white">{perm.name}</p>
                            {perm.description && (
                              <p className="text-xs text-white/50 truncate">{perm.description}</p>
                            )}
                          </div>
                          <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${
                            perm.risk_level === 'high' ? 'bg-red-500/15 text-red-300' :
                            perm.risk_level === 'medium' ? 'bg-amber-500/15 text-amber-300' :
                            'bg-green-500/15 text-green-300'
                          }`}>
                            {perm.category}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {wizardStep === 5 && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-white/80">Assign a room for this agent</p>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={autoCreateRoom}
                        onChange={(e) => setAutoCreateRoom(e.target.checked)}
                        className="h-4 w-4 rounded border-white/15 text-indigo-400 focus:ring-indigo-500/40"
                      />
                      <span className="text-sm text-white/70">Auto-create room</span>
                    </label>
                  </div>
                  {!autoCreateRoom && (
                    <>
                      <select
                        value={selectedRoomId}
                        onChange={(e) => setSelectedRoomId(e.target.value)}
                        className="w-full px-3 py-2 text-sm border border-white/15 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50 bg-white/5"
                      >
                        <option value="">No room (flexible)</option>
                        {rooms.filter((r) => r.status === 'available').map((room) => (
                          <option key={room.id} value={room.id}>{room.name} ({room.room_type ?? 'general'})</option>
                        ))}
                      </select>
                      {rooms.filter((r) => r.status === 'available').length === 0 && (
                        <p className="text-xs text-white/50">No available rooms. Enable auto-create or create a room first.</p>
                      )}
                    </>
                  )}
                  {autoCreateRoom && (
                    <p className="text-xs text-white/50">A new workspace room will be automatically created for this agent.</p>
                  )}
                </div>
              )}

              {wizardStep === 6 && (
                <div className="space-y-4">
                  <p className="text-sm font-medium text-white/80">Review your agent configuration</p>
                  <div className="bg-white/[0.04] rounded-lg p-4 space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-white/50">Template</span>
                      <span className="font-medium text-white">{selectedTemplate.name}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white/50">Name</span>
                      <span className="font-medium text-white">{agentName || '(unnamed)'}</span>
                    </div>
                    {agentDescription && (
                      <div className="text-sm">
                        <span className="text-white/50">Description</span>
                        <p className="text-white mt-1">{agentDescription}</p>
                      </div>
                    )}
                    <div className="flex justify-between text-sm">
                      <span className="text-white/50">Tools</span>
                      <span className="font-medium text-white">{selectedToolIds.length} selected</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white/50">Integrations</span>
                      <span className="font-medium text-white">{selectedIntegrationIds.length} selected</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white/50">Permissions</span>
                      <span className="font-medium text-white">{selectedPermissionIds.length} selected</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white/50">Room</span>
                      <span className="font-medium text-white">
                        {autoCreateRoom ? 'Auto-create' : (selectedRoomId ? getRoomName(selectedRoomId) ?? 'Unknown' : 'Not assigned')}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="px-5 py-3 border-t border-white/10 flex items-center justify-between shrink-0">
              <button
                type="button"
                onClick={prevStep}
                disabled={wizardStep === 0 || isHiring}
                className="px-4 py-2 text-sm font-medium text-white/80 bg-white/10 rounded-lg hover:bg-white/15 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Back
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowWizard(false)}
                  disabled={isHiring}
                  className="px-4 py-2 text-sm font-medium text-white/50 hover:text-white/80 transition-colors"
                >
                  Cancel
                </button>
                {wizardStep < WIZARD_STEPS.length - 1 ? (
                  <button
                    type="button"
                    onClick={nextStep}
                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 transition-colors"
                  >
                    Next
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowConfirmHire(true)}
                    disabled={isHiring || !agentName.trim()}
                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Review & Hire
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {showConfirmHire && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => !isHiring && setShowConfirmHire(false)} />
          <div className="relative bg-[#0d0d1a] border border-white/10 rounded-xl shadow-2xl shadow-black/60 w-full max-w-sm mx-4 overflow-hidden">
            <div className="px-5 py-4">
              <h2 className="text-base font-semibold text-white">Confirm Hire</h2>
              <p className="mt-2 text-sm text-white/70">
                Hire <strong>{agentName}</strong> as a {selectedTemplate?.name}? This will create the agent and assign it a workspace.
              </p>
            </div>
            <div className="px-5 py-3 bg-white/[0.04] flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowConfirmHire(false)}
                disabled={isHiring}
                className="px-4 py-2 text-sm font-medium text-white/80 bg-white/5 border border-white/15 rounded-lg hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleHire}
                disabled={isHiring}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 disabled:opacity-50 transition-colors"
              >
                {isHiring ? 'Hiring...' : 'Hire Agent'}
              </button>
            </div>
          </div>
        </div>
      )}

      {deletingAgent && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => !isDeleting && setDeletingAgent(null)} />
          <div className="relative bg-[#0d0d1a] border border-white/10 rounded-xl shadow-2xl shadow-black/60 w-full max-w-sm mx-4 overflow-hidden">
            <div className="px-5 py-4">
              <h2 className="text-base font-semibold text-white">Fire Agent</h2>
              <p className="mt-2 text-sm text-white/70">
                Are you sure you want to fire <strong>{deletingAgent.name}</strong>? This will permanently remove the agent and its configuration. This action cannot be undone.
              </p>
            </div>
            <div className="px-5 py-3 bg-white/[0.04] flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletingAgent(null)}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-white/80 bg-white/5 border border-white/15 rounded-lg hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-500 disabled:opacity-50 transition-colors"
              >
                {isDeleting ? 'Firing...' : 'Fire Agent'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentsPage
