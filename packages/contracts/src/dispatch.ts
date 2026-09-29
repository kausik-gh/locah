/**
 * Dispatch execution contract (Capability Universe §13).
 *
 * The order is the sale. Fulfilment is the pickup or delivery choice.
 * Dispatch is the physical work after that choice exists. Python status
 * names in platform_core.dispatch.service stay in step with this file.
 */

export const DISPATCH_STATUSES = [
  'unassigned',
  'assigned',
  'picked_up',
  'out_for_delivery',
  'delivered',
  'failed',
] as const

export type DispatchStatus = (typeof DISPATCH_STATUSES)[number]

export const DISPATCH_KINDS = ['delivery', 'pickup'] as const

export type DispatchKind = (typeof DISPATCH_KINDS)[number]

/** The five steps a customer reads. Failed is a separate attention state. */
export const CUSTOMER_TRACK_STEPS = [
  'placed',
  'preparing',
  'picked_up',
  'on_the_way',
  'delivered',
] as const

export type CustomerTrackStep = (typeof CUSTOMER_TRACK_STEPS)[number]

/** Owner / dispatcher columns. Out now covers pickup and on-the-way. */
export const DISPATCH_COLUMNS = [
  { key: 'unassigned', label: 'Unassigned', statuses: ['unassigned'] },
  { key: 'assigned', label: 'Assigned', statuses: ['assigned'] },
  { key: 'out_now', label: 'Out now', statuses: ['picked_up', 'out_for_delivery'] },
  { key: 'delivered', label: 'Delivered', statuses: ['delivered'] },
  { key: 'attention', label: 'Failed / attention', statuses: ['failed'] },
] as const

export interface DispatchTimestamps {
  planned_at: string | null
  assigned_at: string | null
  picked_up_at: string | null
  out_for_delivery_at: string | null
  delivered_at: string | null
  failed_at: string | null
}

/**
 * What the public tracking page may show.
 * live_location stays null until a real device posts a coordinate.
 * status_only means there is no live fix — show the status and the times.
 */
export interface DispatchTracking {
  status: DispatchStatus
  reached_step: CustomerTrackStep
  failed: boolean
  timestamps: DispatchTimestamps
  live_location: null | {
    lat: number
    lng: number
    recorded_at: string
  }
  location_mode: 'status_only' | 'device'
  partner_first_name: string | null
}

/**
 * Events messaging already consumes, plus the dispatch-owned assigned event.
 * Assigned has no existing customer template; the others reuse the fulfilment
 * event types messaging already subscribes to. Messaging internals are not
 * extended here.
 */
export const DISPATCH_NOTIFY_EVENTS = {
  assigned: 'dispatch.assigned',
  out_for_delivery: 'fulfilment.status_changed',
  delivered: 'fulfilment.delivered',
  failed: 'fulfilment.failed',
} as const
