import { create } from 'zustand'
import { wsClient } from '../services/websocket'

export interface RealtimeEvent {
  type: string
  event_type?: string
  data?: Record<string, any>
  timestamp?: string
  [key: string]: any
}

interface RealtimeState {
  connected: boolean
  events: RealtimeEvent[]
  lastEvent: RealtimeEvent | null
  agentStatuses: Map<string, { status: string; room_id?: string }>
  taskUpdates: Map<string, { status: string; title?: string }>
  pendingApprovals: number
  unreadNotifications: number
  maxEvents: number

  connect: (roomId: string, token?: string) => void
  connectDashboard: (token?: string) => void
  connectUser: (userId: string, token?: string) => void
  disconnect: () => void
  subscribe: (type: string, handler: (event: any) => void) => () => void
  addEvent: (event: RealtimeEvent) => void
  setPendingApprovals: (count: number) => void
  setUnreadNotifications: (count: number) => void
  clearEvents: () => void
}

export const useRealtimeStore = create<RealtimeState>((set) => ({
  connected: false,
  events: [],
  lastEvent: null,
  agentStatuses: new Map(),
  taskUpdates: new Map(),
  pendingApprovals: 0,
  unreadNotifications: 0,
  maxEvents: 200,

  connect: (roomId, token) => {
    wsClient.connect(roomId, token)
  },

  connectDashboard: (token) => {
    wsClient.connectDashboard(token)
  },

  connectUser: (userId, token) => {
    wsClient.connectUser(userId, token)
  },

  disconnect: () => {
    wsClient.disconnect()
    set({ connected: false })
  },

  subscribe: (type, handler) => {
    return wsClient.on(type, handler)
  },

  addEvent: (event) => {
    set((state) => {
      const events = [event, ...state.events].slice(0, state.maxEvents)
      const agentStatuses = new Map(state.agentStatuses)
      const taskUpdates = new Map(state.taskUpdates)

      if (event.type === 'agent_status_changed' || event.event_type === 'agent_status_changed') {
        const agentId = event.data?.agent_id || event.agent_id
        if (agentId) {
          agentStatuses.set(agentId, {
            status: event.data?.status || event.status || '',
            room_id: event.data?.room_id || event.room_id,
          })
        }
      }

      if (event.type === 'task_created' || event.type === 'task_updated' ||
          event.type === 'task_completed' || event.type === 'task_failed' ||
          event.event_type?.startsWith('task_')) {
        const taskId = event.data?.task_id || event.task_id
        if (taskId) {
          taskUpdates.set(taskId, {
            status: event.data?.status || event.status || '',
            title: event.data?.title || event.title,
          })
        }
      }

      return { events, lastEvent: event, agentStatuses, taskUpdates }
    })
  },

  setPendingApprovals: (count) => set({ pendingApprovals: count }),
  setUnreadNotifications: (count) => set({ unreadNotifications: count }),
  clearEvents: () => set({ events: [], lastEvent: null }),
}))

export function initRealtime() {
  const store = useRealtimeStore.getState()

  wsClient.on('connected', () => {
    useRealtimeStore.setState({ connected: true })
  })

  wsClient.on('disconnected', () => {
    useRealtimeStore.setState({ connected: false })
  })

  wsClient.on('agent_status_changed', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('agent_lifecycle_changed', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('agent_error', (event: RealtimeEvent) => store.addEvent(event))

  wsClient.on('task_created', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('task_updated', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('task_completed', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('task_failed', (event: RealtimeEvent) => store.addEvent(event))

  wsClient.on('approval_created', (event: RealtimeEvent) => {
    store.addEvent(event)
    useRealtimeStore.setState((s) => ({ pendingApprovals: s.pendingApprovals + 1 }))
  })
  wsClient.on('approval_approved', (event: RealtimeEvent) => {
    store.addEvent(event)
    useRealtimeStore.setState((s) => ({ pendingApprovals: Math.max(0, s.pendingApprovals - 1) }))
  })
  wsClient.on('approval_rejected', (event: RealtimeEvent) => {
    store.addEvent(event)
    useRealtimeStore.setState((s) => ({ pendingApprovals: Math.max(0, s.pendingApprovals - 1) }))
  })

  wsClient.on('notification_created', (event: RealtimeEvent) => {
    store.addEvent(event)
    useRealtimeStore.setState((s) => ({ unreadNotifications: s.unreadNotifications + 1 }))
  })

  wsClient.on('email_received', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('room_status_changed', (event: RealtimeEvent) => store.addEvent(event))

  wsClient.on('activity_logged', (event: RealtimeEvent) => store.addEvent(event))

  wsClient.on('integration_connected', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('integration_disconnected', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('integration_error', (event: RealtimeEvent) => store.addEvent(event))

  wsClient.on('tool_execution_started', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('tool_execution_completed', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('tool_execution_failed', (event: RealtimeEvent) => store.addEvent(event))

  wsClient.on('knowledge_updated', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('system_alert', (event: RealtimeEvent) => store.addEvent(event))

  wsClient.on('message', (event: RealtimeEvent) => store.addEvent(event))
  wsClient.on('*', (event: RealtimeEvent) => store.addEvent(event))
}
