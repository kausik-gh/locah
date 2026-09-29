import { platformUrl } from '@platform/config'

const base = `${platformUrl('api')}/v1/public/documents`

export type PublicFormField = {
  key: string
  type: string
  label: string
  required?: boolean
  help_text?: string
  options?: string[]
  order?: number
}

export type DocumentRequestView = {
  id: string
  title: string
  request_type: 'form' | 'upload'
  status: 'open' | 'fulfilled' | string
  expires_at: string
  business_name?: string | null
  form?: {
    id: string
    version: number
    fields: PublicFormField[]
    consent_text?: string | null
    guardian_required?: boolean
  }
}

export async function fetchDocumentRequest(slug: string, token: string): Promise<DocumentRequestView | null> {
  const res = await fetch(`${base}/${encodeURIComponent(slug)}/${encodeURIComponent(token)}`, { cache: 'no-store' })
  if (!res.ok) return null
  const json = await res.json()
  return json.data as DocumentRequestView
}
