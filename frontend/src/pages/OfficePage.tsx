import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import type { OfficeRoom, AIAgent, Task, AgentActivity, Approval, CreateRoomRequest } from '../types'
import { officeService } from '../services/office'
import RoomDetail from '../components/office/RoomDetail'
import RoomDashboard from '../components/office/RoomDashboard'
import CreateRoomModal from '../components/office/CreateRoomModal'
import SpotlightCards from '../components/kokonutui/spotlight-cards'
import type { SpotlightItem } from '../components/kokonutui/spotlight-cards'
import { useRealtimeStore } from '../stores/useRealtimeStore'
import {
  User, Mail, MessageSquare, LayoutGrid, BookOpen,
  Plus, RefreshCw, Search, AlertTriangle
} from 'lucide-react'

const POLL_INTERVAL = 15000
const ROOM_POLL_INTERVAL = 5000
const APPROVALS_POLL_INTERVAL = 10000

const ROOM_TYPE_CONFIG: Record<string, { icon: typeof User; label: string; color: string }> = {
  ceo_office: { icon: User, label: 'CEO Office', color: '#8b5cf6' },
  email_support: { icon: Mail, label: 'Email Support', color: '#3b82f6' },
  meeting_room: { icon: MessageSquare, label: 'Meeting Room', color: '#10b981' },
  workspace: { icon: LayoutGrid, label: 'Workspace', color: '#f59e0b' },
  reception: { icon: BookOpen, label: 'Reception', color: '#ec4899' },
}

const STATUS_COLORS: Record<string, string> = {
  online_active: '#22c55e',
  online_inactive: '#f59e0b',
  offline: '#94a3b8',
  needs_attention: '#ef4444',
  error: '#ef4444',
}

function getRoomVisualStatus(room: OfficeRoom, agents: AIAgent[]): string {
  const roomAgents = agents.filter(a => a.room_id === room.id)
  if (roomAgents.some(a => a.lifecycle_status === 'error')) return 'error'
  if (roomAgents.some(a => a.status === 'busy')) return 'needs_attention'
  if (roomAgents.some(a => a.status === 'active')) return 'online_active'
  if (roomAgents.length > 0) return 'online_inactive'
  return 'offline'
}

const OfficePage = () => {
  const [rooms, setRooms] = useState<OfficeRoom[]>([])
  const [agents, setAgents] = useState<AIAgent[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [activities, setActivities] = useState<AgentActivity[]>([])
  const [selectedRoom, setSelectedRoom] = useState<OfficeRoom | null>(null)
  const [enteredRoom, setEnteredRoom] = useState<OfficeRoom | null>(null)
  const [_enteredFrom, setEnteredFrom] = useState<OfficeRoom | null>(null)
  const [ceoRoomApprovals, setCeoRoomApprovals] = useState<Approval[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // In-flight guard: if a fetch is still running (slow DB), skip the tick
  // instead of stacking another 4 parallel requests on top of it.
  const fetchingRef = useRef(false)

  const fetchData = useCallback(async (silent = false) => {
    if (fetchingRef.current) return
    if (!silent) setIsLoading(true)
    setError(null)
    fetchingRef.current = true

    try {
      const results = await Promise.allSettled([
        officeService.getRooms(),
        officeService.getAgents(),
        officeService.getTasks(),
        officeService.getAllActivity(200),
      ])

      const [roomsResult, agentsResult, tasksResult, activityResult] = results

      if (roomsResult.status === 'fulfilled' && roomsResult.value.success && roomsResult.value.data) {
        setRooms(roomsResult.value.data)
      } else if (roomsResult.status === 'rejected' || (roomsResult.status === 'fulfilled' && !roomsResult.value.success)) {
        setError(roomsResult.status === 'fulfilled' ? (roomsResult.value.error ?? 'Failed to load office data') : 'Failed to load office data')
      }

      if (agentsResult.status === 'fulfilled' && agentsResult.value.success && agentsResult.value.data) {
        setAgents(agentsResult.value.data)
      }

      if (tasksResult.status === 'fulfilled' && tasksResult.value.success && tasksResult.value.data) {
        setTasks(tasksResult.value.data)
      }

      if (activityResult.status === 'fulfilled' && activityResult.value.success && activityResult.value.data) {
        setActivities(activityResult.value.data)
      }

      setLastRefresh(new Date())
    } finally {
      fetchingRef.current = false
      setIsLoading(false)
    }
  }, [])

  // Skip polling entirely while the tab is hidden (browser background tabs
  // were piling up queued requests against the slow remote DB).
  useEffect(() => {
    const onVisibility = () => {
      if (!document.hidden) fetchData(true)
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [fetchData])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Poll fast while a room dashboard is open so every tab (Overview,
  // Tasks, Activity, Approvals, Performance, Controls) stays live without
  // a manual refresh; slower while browsing the rooms grid.
  useEffect(() => {
    const interval = enteredRoom ? ROOM_POLL_INTERVAL : POLL_INTERVAL
    pollRef.current = setInterval(() => {
      fetchData(true)
    }, interval)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchData, enteredRoom])

  // Real-time: update agents/tasks/approvals incrementally from WS events.
  // Any relevant event also triggers a debounced silent refresh so ALL
  // dashboard tabs pick up fresh data within ~1s instead of waiting for
  // the next poll.
  const silentRefreshRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const scheduleSilentRefresh = useCallback(() => {
    if (silentRefreshRef.current) clearTimeout(silentRefreshRef.current)
    silentRefreshRef.current = setTimeout(() => fetchData(true), 600)
  }, [fetchData])

  useEffect(() => {
    const unsubAgent = useRealtimeStore.getState().subscribe('agent_status_changed', (event: any) => {
      const { agent_id, status } = event.data || event
      if (agent_id) {
        setAgents(prev => prev.map(a => a.id === agent_id ? { ...a, status } : a))
      }
      scheduleSilentRefresh()
    })
    const unsubAgentLifecycle = useRealtimeStore.getState().subscribe('agent_lifecycle_changed', (event: any) => {
      const { agent_id, lifecycle_status } = event.data || event
      if (agent_id) {
        setAgents(prev => prev.map(a => a.id === agent_id ? { ...a, lifecycle_status } : a))
      }
      scheduleSilentRefresh()
    })
    const unsubTask = useRealtimeStore.getState().subscribe('task_created', (event: any) => {
      const { task_id, title, status, agent_id } = event.data || event
      if (task_id) {
        setTasks(prev => {
          if (prev.some(t => t.id === task_id)) return prev
          return [{ id: task_id, title, status, agent_id } as Task, ...prev].slice(0, 200)
        })
      }
      scheduleSilentRefresh()
    })
    const unsubTaskUpdate = useRealtimeStore.getState().subscribe('task_completed', (event: any) => {
      const { task_id, status } = event.data || event
      if (task_id) {
        setTasks(prev => prev.map(t => t.id === task_id ? { ...t, status } : t))
      }
      scheduleSilentRefresh()
    })
    const unsubTaskFailed = useRealtimeStore.getState().subscribe('task_failed', (event: any) => {
      const { task_id, status } = event.data || event
      if (task_id) {
        setTasks(prev => prev.map(t => t.id === task_id ? { ...t, status } : t))
      }
      scheduleSilentRefresh()
    })
    const unsubTaskUpdated = useRealtimeStore.getState().subscribe('task_updated', (event: any) => {
      const { task_id, title, status } = event.data || event
      if (task_id) {
        setTasks(prev => prev.map(t => t.id === task_id
          ? { ...t, ...(title ? { title } : {}), ...(status ? { status } : {}) }
          : t
        ))
      }
      scheduleSilentRefresh()
    })
    const unsubApproval = useRealtimeStore.getState().subscribe('approval_created', (event: any) => {
      const { approval_id, agent_id, action, risk_level } = event.data || event
      if (enteredRoom) {
        const roomAgents = agents.filter(a => a.room_id === enteredRoom.id)
        if (roomAgents.some(a => a.id === agent_id)) {
          setCeoRoomApprovals(prev => {
            if (prev.some(a => a.id === approval_id)) return prev
            return [{ id: approval_id, agent_id, action, risk_level, status: 'pending' } as Approval, ...prev]
          })
        }
      }
      scheduleSilentRefresh()
    })
    // Tool executions change activities/tasks the moment they run —
    // refresh silently so the Activity tab updates instantly.
    const unsubsTool = ['tool_execution_started', 'tool_execution_completed', 'tool_execution_failed']
      .map(evt => useRealtimeStore.getState().subscribe(evt, () => scheduleSilentRefresh()))

    // Activity rows stream in over WebSocket the instant the backend
    // persists them — apply directly for zero-latency Activity tab.
    const unsubActivity = useRealtimeStore.getState().subscribe('activity_logged', (event: any) => {
      const d = event.data || event
      const activityId = d.activity_id || d.id
      if (!activityId || !d.agent_id) return
      setActivities(prev => {
        if (prev.some(a => a.id === activityId)) return prev
        return [{
          id: activityId,
          agent_id: d.agent_id,
          activity_type: d.activity_type ?? 'tool_used',
          description: d.description ?? null,
          task_id: d.task_id ?? null,
          tool_name: d.tool_name ?? null,
          status: d.status ?? null,
          created_at: d.created_at ?? d.timestamp ?? new Date().toISOString(),
        } as AgentActivity, ...prev].slice(0, 200)
      })
      // Keep agents/tasks consistent too (last_active_at changed).
      scheduleSilentRefresh()
    })

    return () => {
      unsubAgent()
      unsubAgentLifecycle()
      unsubTask()
      unsubTaskUpdate()
      unsubTaskFailed()
      unsubTaskUpdated()
      unsubApproval()
      unsubsTool.forEach(unsub => unsub())
      unsubActivity()
    }
  }, [enteredRoom, agents, scheduleSilentRefresh])

  // Memoize agent IDs for the room to avoid re-fetching on every agents state change
  const currentRoomAgentIds = useMemo(() => {
    if (!enteredRoom) return []
    return agents.filter(a => a.room_id === enteredRoom.id).map(a => a.id)
  }, [enteredRoom, agents])

  useEffect(() => {
    if (!enteredRoom || currentRoomAgentIds.length === 0) {
      setCeoRoomApprovals([])
      return
    }

    const loadApprovals = () => {
      Promise.all(currentRoomAgentIds.map(id => officeService.getApprovals('pending', id)))
        .then(results => {
          const allApprovals = results
            .filter(r => r.success && r.data)
            .flatMap(r => r.data ?? [])
          setCeoRoomApprovals(allApprovals)
        })
        .catch(() => {})
    }

    loadApprovals()
    // Approvals tab must reflect decided/pending changes quickly.
    const approvalsTimer = setInterval(loadApprovals, APPROVALS_POLL_INTERVAL)
    return () => clearInterval(approvalsTimer)
  }, [enteredRoom, currentRoomAgentIds])

  // Re-render every 30s so relative labels ("3m ago", "just now") in every
  // tab stay fresh even when nothing else changes.
  const [, setTick] = useState(0)
  useEffect(() => {
    const tickTimer = setInterval(() => setTick(t => t + 1), 30000)
    return () => clearInterval(tickTimer)
  }, [])

  const handleRoomSelect = useCallback((room: OfficeRoom) => {
    setSelectedRoom((prev) => (prev?.id === room.id ? null : room))
  }, [])

  const handleCloseDetail = useCallback(() => {
    setSelectedRoom(null)
  }, [])

  const handleEnterRoom = useCallback((room: OfficeRoom) => {
    const ceoOffice = rooms.find(r => r.room_type === 'ceo_office') ?? null
    setEnteredFrom(ceoOffice)
    setEnteredRoom(room)
    setSelectedRoom(null)
  }, [rooms])

  const handleLeaveRoom = useCallback(() => {
    setEnteredRoom(null)
    setEnteredFrom(null)
    setCeoRoomApprovals([])
  }, [])

  const handleCreateRoom = useCallback(async (data: CreateRoomRequest) => {
    const result = await officeService.createRoom(data)
    if (!result.success) {
      throw new Error(result.error ?? 'Failed to create room')
    }
    await fetchData()
  }, [fetchData])

  const handleDeleteRoom = useCallback(async (roomId: string) => {
    const result = await officeService.deleteRoom(roomId)
    if (result.success) {
      setSelectedRoom(null)
      await fetchData()
    }
    return result
  }, [fetchData])

  const handleAssignAgent = useCallback(async (agentId: string, roomId: string | null) => {
    const result = await officeService.updateAgent(agentId, { room_id: roomId })
    if (result.success) {
      await fetchData(true)
    }
    return result
  }, [fetchData])

  const handleLifecycleAction = useCallback(async (agentId: string, action: 'pause' | 'resume' | 'disable' | 'archive' | 'restart', reason?: string) => {
    const result = await officeService.updateAgentLifecycle(agentId, action, reason)
    if (result.success) {
      await fetchData(true)
    }
    return result
  }, [fetchData])

  const handleApproveApproval = useCallback(async (id: string) => {
    const result = await officeService.approveApproval(id)
    if (result.success) {
      if (enteredRoom) {
        const roomAgents = agents.filter(a => a.room_id === enteredRoom.id)
        const agentIds = roomAgents.map(a => a.id)
        const approvalResults = await Promise.all(agentIds.map(aid => officeService.getApprovals('pending', aid)))
        const allApprovals = approvalResults.filter(r => r.success && r.data).flatMap(r => r.data ?? [])
        setCeoRoomApprovals(allApprovals)
      }
      await fetchData(true)
    }
    return result
  }, [fetchData, enteredRoom, agents])

  const handleRejectApproval = useCallback(async (id: string) => {
    const result = await officeService.rejectApproval(id)
    if (result.success) {
      if (enteredRoom) {
        const roomAgents = agents.filter(a => a.room_id === enteredRoom.id)
        const agentIds = roomAgents.map(a => a.id)
        const approvalResults = await Promise.all(agentIds.map(aid => officeService.getApprovals('pending', aid)))
        const allApprovals = approvalResults.filter(r => r.success && r.data).flatMap(r => r.data ?? [])
        setCeoRoomApprovals(allApprovals)
      }
      await fetchData(true)
    }
    return result
  }, [fetchData, enteredRoom, agents])

  // Build spotlight card items from rooms
  const spotlightItems = useMemo<SpotlightItem[]>(() => {
    const filtered = searchQuery
      ? rooms.filter(r => r.name.toLowerCase().includes(searchQuery.toLowerCase()) || r.description?.toLowerCase().includes(searchQuery.toLowerCase()))
      : rooms

    return filtered.map(room => {
      const config = ROOM_TYPE_CONFIG[room.room_type ?? 'workspace'] ?? ROOM_TYPE_CONFIG.workspace
      const roomAgents = agents.filter(a => a.room_id === room.id)
      const visualStatus = getRoomVisualStatus(room, agents)
      const statusColor = STATUS_COLORS[visualStatus] ?? '#94a3b8'

      const agentList = roomAgents.length > 0
        ? roomAgents.map(a => a.name).join(', ')
        : 'No agents assigned'

      const activeCount = roomAgents.filter(a => a.status === 'active' || a.status === 'busy').length
      const statusText = visualStatus === 'online_active' ? `${activeCount} active`
        : visualStatus === 'online_inactive' ? `${roomAgents.length} idle`
        : visualStatus === 'needs_attention' ? 'Needs attention'
        : visualStatus === 'error' ? 'Error'
        : 'Empty'

      return {
        icon: config.icon,
        title: room.name,
        description: `${config.label} \u00b7 ${statusText}\n${agentList}`,
        color: statusColor,
        onClick: () => handleRoomSelect(room),
      }
    })
  }, [rooms, agents, searchQuery, handleRoomSelect])

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto" />
          <p className="mt-3 text-sm text-gray-500">Loading office...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-sm">
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
            {error}
          </div>
          <button
            type="button"
            onClick={() => fetchData()}
            className="px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const onlineAgents = agents.filter(a => a.lifecycle_status === 'active' || a.lifecycle_status === 'paused')
  const errorAgents = agents.filter(a => a.lifecycle_status === 'error')

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col pb-20">
      {/* Main Content */}
      <div className="flex-1 overflow-y-auto bg-[#06060f]">
        {/* Top Bar */}
        <div className="sticky top-0 z-10 bg-[#06060f]/80 backdrop-blur-xl border-b border-white/6">
          <div className="flex items-center justify-between px-6 py-3">
            <div className="flex items-center gap-4">
              <div>
                <h1 className="text-sm font-semibold text-white tracking-tight">Virtual Office</h1>
                <p className="text-[11px] text-white/40">{rooms.length} rooms \u00b7 {onlineAgents.length} agents online</p>
              </div>
              {errorAgents.length > 0 && (
                <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/10 border border-red-500/20">
                  <AlertTriangle size={12} className="text-red-400" />
                  <span className="text-[11px] text-red-400">{errorAgents.length} error</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* Search */}
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/30" />
                <input
                  type="text"
                  placeholder="Search rooms..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-xs bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/30 focus:outline-none focus:border-white/20 w-48"
                />
              </div>

              {/* Refresh */}
              <button
                type="button"
                onClick={() => fetchData(true)}
                className="p-1.5 rounded-lg bg-white/5 border border-white/10 text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                title="Refresh"
              >
                <RefreshCw size={14} />
              </button>

              {/* Add Room */}
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 transition-colors"
              >
                <Plus size={14} />
                Add Room
              </button>

              {/* Last updated */}
              <span className="text-[11px] text-white/30 ml-2">
                {lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        </div>

        {/* Spotlight Cards Grid */}
        <div className="p-6">
          {spotlightItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24">
              <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-4">
                <LayoutGrid size={28} className="text-white/20" />
              </div>
              <p className="text-sm text-white/40 mb-1">No rooms found</p>
              <p className="text-xs text-white/20 mb-4">
                {searchQuery ? 'Try a different search' : 'Create your first room to get started'}
              </p>
              {!searchQuery && (
                <button
                  type="button"
                  onClick={() => setShowCreateModal(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 transition-colors"
                >
                  <Plus size={16} />
                  Create Room
                </button>
              )}
            </div>
          ) : (
            <SpotlightCards
              items={spotlightItems}
              eyebrow="Rooms"
              heading="Your AI Workspace"
              className="bg-transparent border-0"
            />
          )}
        </div>

        {/* Quick Stats */}
        <div className="px-6 pb-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-xl bg-white/3 border border-white/6 p-4">
              <p className="text-[11px] text-white/40 uppercase tracking-wider mb-1">Total Rooms</p>
              <p className="text-2xl font-semibold text-white">{rooms.length}</p>
            </div>
            <div className="rounded-xl bg-white/3 border border-white/6 p-4">
              <p className="text-[11px] text-white/40 uppercase tracking-wider mb-1">Online Agents</p>
              <p className="text-2xl font-semibold text-green-400">{onlineAgents.length}</p>
            </div>
            <div className="rounded-xl bg-white/3 border border-white/6 p-4">
              <p className="text-[11px] text-white/40 uppercase tracking-wider mb-1">Active Tasks</p>
              <p className="text-2xl font-semibold text-amber-400">{tasks.filter(t => t.status === 'running').length}</p>
            </div>
            <div className="rounded-xl bg-white/3 border border-white/6 p-4">
              <p className="text-[11px] text-white/40 uppercase tracking-wider mb-1">Pending Approvals</p>
              <p className="text-2xl font-semibold text-purple-400">{tasks.filter(t => t.status === 'waiting_approval').length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Detail Popup */}
      {selectedRoom && !enteredRoom && (
        <div className="fixed inset-0 z-30 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={handleCloseDetail} />
          <div className="relative w-full max-w-md mx-4">
            <RoomDetail
              room={selectedRoom}
              agents={agents}
              tasks={tasks}
              activities={activities}
              onClose={handleCloseDetail}
              onEnter={handleEnterRoom}
              onDelete={handleDeleteRoom}
              onAssignAgent={handleAssignAgent}
            />
          </div>
        </div>
      )}

      {/* Agent Dashboard Overlay */}
      {enteredRoom && (
        <RoomDashboard
          room={enteredRoom}
          agents={agents}
          tasks={tasks}
          activities={activities}
          pendingApprovals={ceoRoomApprovals}
          onLeave={handleLeaveRoom}
          onLifecycleAction={handleLifecycleAction}
          onApproveApproval={handleApproveApproval}
          onRejectApproval={handleRejectApproval}
          onDelete={handleDeleteRoom}
          onRefresh={fetchData}
        />
      )}

      {/* Create Room Modal */}
      <CreateRoomModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSubmit={handleCreateRoom}
      />
    </div>
  )
}

export default OfficePage
