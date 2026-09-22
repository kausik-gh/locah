// Canonical API and Event contracts
export type * from './interview'
export interface EventEnvelope<T = Record<string, any>> {
  id: string
  businessId: string | null
  eventType: string
  eventVersion: string
  payload: T
  correlationId: string | null
  causationId: string | null
  occurredAt: string
}
