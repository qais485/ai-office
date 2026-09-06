import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { AgentActivity } from '../types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Parse a server timestamp into a real Date.
 *
 * The backend returns most timestamps without an explicit UTC offset
 * (legacy string columns like last_active_at, and raw ISO strings
 * lacking a zone). JavaScript's `new Date()` treats offset-less strings
 * as LOCAL time, which skewed every "x ago" label by the viewer's UTC
 * offset (e.g. "5 minutes ago" showed as "4h ago" at UTC+4:30). Backend
 * timestamps are always UTC, so strings without an explicit offset get
 * 'Z' appended before parsing.
 */
export function parseServerDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null
  if (value instanceof Date) return isNaN(value.getTime()) ? null : value
  let s = String(value).trim()
  if (!s) return null
  // Already has an offset (Z or ±hh:mm) — parse as-is.
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(s)
  if (!hasOffset) {
    // Date-only string → UTC midnight; otherwise assume UTC.
    s = /^\d{4}-\d{2}-\d{2}$/.test(s) ? `${s}T00:00:00Z` : `${s}Z`
  }
  const d = new Date(s)
  return isNaN(d.getTime()) ? null : d
}

/** Normalize any legacy timestamp field to a UTC-marked ISO string. */
export function toServerIso(value: string | Date | null | undefined): string | null {
  const d = parseServerDate(value)
  return d ? d.toISOString() : null
}

export function formatTimeAgo(dateStr: string | Date | null | undefined): string {
  const date = parseServerDate(dateStr)
  if (!date) return '—'
  const diff = Date.now() - date.getTime()
  const secs = Math.floor(diff / 1000)
  if (secs < 5) return 'just now'
  const mins = Math.floor(secs / 60)
  if (mins < 1) return `${secs}s ago`
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks}w ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`
  return `${Math.floor(days / 365)}y ago`
}

export function getLatestActivity(activities: AgentActivity[], agentId: string): AgentActivity | null {
  const agentActivities = activities.filter(a => a.agent_id === agentId)
  if (agentActivities.length === 0) return null
  return agentActivities.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
}

/**
 * Short, human label for an activity row (max one phrase, no raw email
 * addresses or subjects). Full descriptions stay available via tooltips
 * and the timeline.
 */
export function shortActivityLabel(activity: Pick<AgentActivity, 'activity_type' | 'description' | 'status' | 'tool_name'>): string {
  const desc = (activity.description ?? '').trim()
  const lower = desc.toLowerCase()
  const type = activity.activity_type

  if (lower.startsWith('failed')) return 'Failed processing an email'
  if (lower.startsWith('reply drafted')) return 'Reply awaiting approval'
  if (lower.startsWith('responded to email')) return 'Replied to an email'
  if (lower.startsWith('reviewed')) return 'Reviewed an email — no action needed'
  if (lower.startsWith('executed')) return activity.tool_name ? `Used ${activity.tool_name}` : 'Executed an action'
  if (lower.startsWith('instruction')) return 'Ran an instruction'
  if (type === 'task_completed') return 'Completed a task'
  if (type === 'task_failed') return 'Task failed'
  if (type === 'task_created') return 'Task created'
  if (type === 'tool_used' || type === 'tool_executed') return activity.tool_name ? `Used ${activity.tool_name}` : 'Used a tool'
  if (type === 'approval_requested') return 'Requested approval'

  // Fallback: first segment before " — " keeps it to one phrase.
  return desc.split(' — ')[0] || type
}
