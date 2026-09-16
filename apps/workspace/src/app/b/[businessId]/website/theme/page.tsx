import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { saveThemeNav } from './actions'

export const dynamic = 'force-dynamic'

type WebsiteResponse = {
  data: {
    draft: {
      theme: Record<string, unknown>
      navigation: { label: string; path: string }[]
    }
  }
}

export default async function WebsiteThemePage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<WebsiteResponse>(`/v1/b/${params.businessId}/website`, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Theme, Navigation & Branding" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Website" />
      </div>
    )
  }
  const theme = res.data.data.draft.theme || {}
  const navigation = res.data.data.draft.navigation || []

  return (
    <div>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Theme, Navigation & Branding</h1>
      <p style={{ marginBottom: '1rem' }}>
        Set your colours and choose which pages appear in your website navigation.
      </p>
      <form action={saveThemeNav} style={{ maxWidth: '36rem', display: 'grid', gap: '0.75rem' }}>
        <input type="hidden" name="businessId" value={params.businessId} />
        <label>
          Primary color
          <input
            name="primary_color"
            defaultValue={String(theme.primary_color || '#0F766E')}
            style={{ display: 'block', width: '100%', marginTop: '0.25rem', padding: '0.4rem' }}
          />
        </label>
        <label>
          Accent color
          <input
            name="accent_color"
            defaultValue={String(theme.accent_color || '#F59E0B')}
            style={{ display: 'block', width: '100%', marginTop: '0.25rem', padding: '0.4rem' }}
          />
        </label>
        <label>
          Navigation JSON
          <textarea
            name="navigation_json"
            defaultValue={JSON.stringify(navigation, null, 2)}
            rows={8}
            style={{ display: 'block', width: '100%', marginTop: '0.25rem', padding: '0.4rem' }}
          />
        </label>
        <button type="submit">Save theme & navigation</button>
      </form>
    </div>
  )
}
