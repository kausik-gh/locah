export interface LogMessage {
  message: string
  correlationId?: string
  businessId?: string
  identityId?: string
  service?: string
  module?: string
  durationMs?: number
  [key: string]: any
}

export const logger = {
  info(msg: LogMessage) {
    console.log(JSON.stringify({ level: 'info', timestamp: new Date().toISOString(), ...msg }))
  },
  warn(msg: LogMessage) {
    console.warn(JSON.stringify({ level: 'warn', timestamp: new Date().toISOString(), ...msg }))
  },
  error(msg: LogMessage) {
    console.error(JSON.stringify({ level: 'error', timestamp: new Date().toISOString(), ...msg }))
  },
}
