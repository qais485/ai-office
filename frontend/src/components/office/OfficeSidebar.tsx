import type { OfficeRoom, AIAgent } from '../../types'
import {
  User, Mail, MessageSquare, LayoutGrid, BookOpen
} from 'lucide-react'

const ROOM_TYPE_ICONS: Record<string, typeof User> = {
  ceo_office: User,
  email_support: Mail,
  meeting_room: MessageSquare,
  workspace: LayoutGrid,
  reception: BookOpen,
}

const ROOM_TYPE_LABELS: Record<string, string> = {
  ceo_office: 'CEO Office',
  email_support: 'Email Support',
  meeting_room: 'Meeting Room',
  workspace: 'Workspace',
  reception: 'Reception',
}

const STATUS_COLORS: Record<string, string> = {
  online_active: 'bg-green-500',
  online_inactive: 'bg-amber-500',
  offline: 'bg-gray-500',
  needs_attention: 'bg-red-500',
  error: 'bg-red-500',
}

function getRoomVisualStatus(room: OfficeRoom, agents: AIAgent[]): string {
  const roomAgents = agents.filter(a => a.room_id === room.id)
  if (roomAgents.some(a => a.lifecycle_status === 'error')) return 'error'
  if (roomAgents.some(a => a.status === 'busy')) return 'needs_attention'
  if (roomAgents.some(a => a.status === 'active')) return 'online_active'
  if (roomAgents.length > 0) return 'online_inactive'
  return 'offline'
}

interface OfficeSidebarProps {
  rooms: OfficeRoom[]
  agents: AIAgent[]
  selectedRoomId: string | null
  onRoomSelect: (room: OfficeRoom) => void
}

export default function OfficeSidebar({ rooms, agents, selectedRoomId, onRoomSelect }: OfficeSidebarProps) {
  return (
    <div className="w-full h-full flex flex-col bg-[#0a0a14] border-r border-white/6">
      <div className="px-4 py-4 border-b border-white/6">
        <h2 className="text-sm font-semibold text-white">Rooms</h2>
        <p className="text-[11px] text-white/40 mt-0.5">{rooms.length} rooms</p>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {rooms.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-sm text-white/30">No rooms yet</p>
          </div>
        ) : (
          <ul className="space-y-0.5 px-2">
            {rooms.map((room) => {
              const isSelected = room.id === selectedRoomId
              const Icon = ROOM_TYPE_ICONS[room.room_type ?? ''] ?? ROOM_TYPE_ICONS.workspace
              const typeLabel = ROOM_TYPE_LABELS[room.room_type ?? ''] ?? 'Room'
              const visualStatus = getRoomVisualStatus(room, agents)
              const statusDot = STATUS_COLORS[visualStatus] ?? 'bg-gray-500'
              const roomAgentCount = agents.filter(a => a.room_id === room.id).length

              return (
                <li key={room.id}>
                  <button
                    type="button"
                    onClick={() => onRoomSelect(room)}
                    className={`w-full flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${
                      isSelected
                        ? 'bg-white/8 text-white'
                        : 'text-white/60 hover:bg-white/4 hover:text-white/80'
                    }`}
                  >
                    <div className="mt-0.5 shrink-0">
                      <Icon size={16} strokeWidth={1.5} className={isSelected ? 'text-indigo-400' : 'text-white/30'} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium truncate">{room.name}</span>
                        <span className={`w-2 h-2 rounded-full shrink-0 ${statusDot}`} />
                      </div>
                      <p className="text-[11px] text-white/30 mt-0.5">{typeLabel}</p>
                      {roomAgentCount > 0 && (
                        <p className="text-[10px] text-white/20 mt-0.5">{roomAgentCount} agent{roomAgentCount !== 1 ? 's' : ''}</p>
                      )}
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
