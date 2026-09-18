import type { Metadata } from 'next'
import {
  AUTH_ERROR_COPY,
  type AuthErrorReason,
  RECOVERABLE_BY_RESEND,
  toAuthFlow,
} from '../auth-errors'
import { AuthErrorPanel } from './AuthErrorPanel'

export const metadata: Metadata = {
  title: 'Confirmation problem — LOCAH',
  robots: { index: false, follow: false },
}

function readReason(value: string | string[] | undefined): AuthErrorReason {
  const raw = Array.isArray(value) ? value[0] : value
  return raw && raw in AUTH_ERROR_COPY ? (raw as AuthErrorReason) : 'unknown'
}

export default function AuthErrorPage({
  searchParams,
}: {
  searchParams: { reason?: string | string[]; flow?: string | string[] }
}) {
  const reason = readReason(searchParams.reason)
  const rawFlow = Array.isArray(searchParams.flow) ? searchParams.flow[0] : searchParams.flow
  return (
    <AuthErrorPanel
      flow={toAuthFlow(rawFlow)}
      copy={AUTH_ERROR_COPY[reason]}
      canResend={RECOVERABLE_BY_RESEND.has(reason)}
    />
  )
}
