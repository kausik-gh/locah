/** Shapes of the WhatsApp & messages API (Capability Universe §9.1, §12.5). */

export type Channel = {
  id: string
  provider: 'meta_cloud' | 'sandbox'
  status: 'pending' | 'connected' | 'disconnected' | 'error'
  display_phone: string | null
  display_name: string | null
  coexistence: boolean
  quality_rating: string | null
  messaging_limit: string | null
  last_error: string | null
  last_webhook_at: string | null
  connected_at: string | null
  sandbox: boolean
}

export type TemplateRow = {
  key: string
  label: string
  category: 'utility' | 'marketing'
  audience: 'customer' | 'staff'
  params: string[]
  bodies: Record<string, string>
  sent_when: string
  phase: string
  status: Record<string, 'submitted' | 'approved' | 'rejected' | 'paused' | null>
}

export type Setup = {
  channel: Channel | null
  connection?: Connection
  meta: { app_id: string; config_id: string; graph_version: string } | null
  meta_ready: boolean
  sandbox_available: boolean
  settings: {
    language: 'en' | 'ta' | 'hi'
    human_pause_hours: number
    customer_updates: Record<string, boolean>
    cod_allowed: boolean
    first_order_cod_cap: number | null
  }
  /** §12.2 entry points: the link with "menu" typed, its QR, what customers can do. */
  entry: { number: string; href: string; label: string; journeys: string[]; test_number: boolean; qr_svg: string } | null
  customer_updates: Record<string, string>
  ladder_updates: Record<string, string>
  languages: Record<string, string>
  templates: TemplateRow[]
  alerts: { mine: { phone: string; kinds: string[]; enabled: boolean } | null; kinds: Record<string, string> }
  meter: { used: number; cap: number | null; period: string } | null
}

export type Conversation = {
  id: string
  phone: string
  name: string
  contact_id: string | null
  state: 'open' | 'closed'
  handler: 'bot' | 'person'
  needs_person: boolean
  topic: string | null
  assigned_to: string | null
  assigned_name: string | null
  unread: number
  last_preview: string | null
  waiting_since: string | null
  waiting_minutes: number | null
  window_open: boolean
  window_closes_at: string | null
  bot_paused_until: string | null
  updated_at: string | null
}

export type Message = {
  id: string
  direction: 'in' | 'out'
  kind: string
  body: string | null
  status: string
  error: string | null
  template_key: string | null
  category: string | null
  sent_via: string | null
  sent_by_name: string | null
  payload: {
    latitude?: number
    longitude?: number
    media_type?: string
    title?: string
    /** Buttons or list rows LOCAH offered (structured journeys, §12.3). */
    options?: { id: string; title: string; description?: string }[]
    reply_kind?: 'button' | 'list'
  }
  at: string | null
}

export type Thread = Conversation & {
  messages: Message[]
  customer: {
    contact_id?: string
    name?: string | null
    phone?: string | null
    orders?: { id: string; number: string; status: string; total: number; at: string }[]
    bookings?: { id: string; number: string; status: string; title: string; at: string }[]
    khata?: { account_id: string; balance: number; credit_limit: number | null } | null
    membership?: { status: string; plan: string; ends_at: string | null } | null
  }
}

export const rupees = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(v)

export function clock(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const today = new Date()
  return d.toDateString() === today.toDateString()
    ? d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })
    : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

/** A moment that matters to the hour (reply window, automation pause). */
export function until(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const time = d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}, ${time}`
}

/** The honest connection state (platform_core/messaging/connection.py). */
export type Connection = {
  messaging: {
    state: string
    reason: string | null
    environment: 'sandbox' | 'production' | null
    label: string | null
    steps: { key: string; label: string; done: boolean }[]
  }
  calling: { state: string; reason: string | null; messaging_active: boolean }
  telephony: { state: string; provider: string | null; reason: string | null }
  templates: { approved: number; approved_utility: number; awaiting_review: number; rejected: number }
  last_webhook_at: string | null
}

export type CallRow = {
  id: string
  channel: 'whatsapp_call' | 'pstn'
  direction: 'inbound' | 'outbound'
  from_number: string | null
  state: string
  handled_by_type: string
  within_business_hours: boolean | null
  started_at: string | null
  duration_seconds: number | null
  note: string | null
}
