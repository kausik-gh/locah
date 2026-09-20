/**
 * How a project reads on screen.
 *
 * Presentation only. Status rules, progress and what may be done next come from
 * the API; this turns them into words. The noun comes from the business's own
 * type — a clinic sees "Case", a studio "Project" — so nothing here hard-codes
 * what the work is called.
 */

export type ProjectSemantics = {
  noun: string
  noun_plural: string
  default_phases: string[]
  typical: boolean
}

export type ProjectPhase = {
  id: string
  name: string
  status: string
  is_milestone: boolean
  due_on: string | null
  completed_at: string | null
  sort_order: number
}

export type ProjectTask = {
  id: string
  phase_id: string | null
  title: string
  description: string | null
  status: string
  assignee_member_id: string | null
  due_on: string | null
  completed_at: string | null
  blocked_reason: string | null
  sort_order: number
  version: number
}

export type ProjectRow = {
  id: string
  reference: string
  title: string
  summary: string | null
  status: string
  priority: string
  customer_contact_id: string | null
  location_id: string | null
  lead_member_id: string | null
  starts_on: string | null
  due_on: string | null
  completed_at: string | null
  cancelled_at: string | null
  on_hold_reason: string | null
  cancellation_reason: string | null
  source_quote_id: string | null
  agreed_value: string | null
  currency: string
  is_open: boolean
  version: number
  created_at: string | null
  task_count?: number
  tasks_done?: number
  progress_percent?: number | null
  phases?: ProjectPhase[]
  tasks?: ProjectTask[]
}

export const STATUS_LABEL: Record<string, string> = {
  draft: 'Not started',
  active: 'In progress',
  on_hold: 'On hold',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

export const STATUS_TONE: Record<string, 'good' | 'warn' | 'bad' | 'neutral' | 'info'> = {
  draft: 'neutral',
  active: 'info',
  on_hold: 'warn',
  completed: 'good',
  cancelled: 'neutral',
}

export const TASK_STATUS_LABEL: Record<string, string> = {
  todo: 'To do',
  in_progress: 'In progress',
  blocked: 'Blocked',
  done: 'Done',
  cancelled: 'Dropped',
}

export const TASK_STATUS_TONE: Record<string, 'good' | 'warn' | 'bad' | 'neutral' | 'info'> = {
  todo: 'neutral',
  in_progress: 'info',
  blocked: 'bad',
  done: 'good',
  cancelled: 'neutral',
}

export const PHASE_STATUS_LABEL: Record<string, string> = {
  pending: 'Not started',
  in_progress: 'In progress',
  done: 'Done',
  skipped: 'Skipped',
}

export const PRIORITY_LABEL: Record<string, string> = {
  low: 'Low',
  normal: 'Normal',
  high: 'High',
  urgent: 'Urgent',
}

export function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status
}

export function money(amount: string | number | null | undefined, currency = 'INR'): string {
  if (amount === null || amount === undefined) return '—'
  const value = typeof amount === 'number' ? amount : Number(amount)
  if (!Number.isFinite(value)) return '—'
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
    }).format(value)
  } catch {
    return `${currency || 'INR'} ${value.toFixed(2)}`
  }
}

/**
 * A plain date, formatted as the calendar date it was stored as.
 *
 * `starts_on` and `due_on` are DATE columns, not instants. Reading them in the
 * viewer's zone would shift a due date across midnight for anybody east or west
 * of the server, so they are formatted in UTC — the zone they mean nothing in,
 * and therefore the only one that gives the date back unchanged.
 */
export function dayLabel(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-GB', {
    timeZone: 'UTC',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** Days until a date, or null. Negative means it has passed. */
export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null
  const then = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`).getTime()
  if (Number.isNaN(then)) return null
  return Math.ceil((then - Date.now()) / 86_400_000)
}

/**
 * Which lifecycle moves to draw.
 *
 * A mirror of the service's transition table, for deciding which buttons exist.
 * The API refuses an illegal move regardless, and its refusal is what the owner
 * sees — this only avoids offering something that cannot work.
 */
export const NEXT_STATUSES: Record<string, string[]> = {
  draft: ['active', 'cancelled'],
  active: ['on_hold', 'completed', 'cancelled'],
  on_hold: ['active', 'cancelled'],
  completed: [],
  cancelled: [],
}

export const STATUS_ACTION_LABEL: Record<string, string> = {
  active: 'Start work',
  on_hold: 'Put on hold',
  completed: 'Mark complete',
  cancelled: 'Cancel',
}
