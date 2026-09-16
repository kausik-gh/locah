import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { updatePreferences, updateRegionalSettings } from './actions'

export const dynamic = 'force-dynamic'

type Settings = {
  timezone?: string
  currency?: string
  country?: string
  language?: string
  version?: number
}

type Preferences = {
  date_format?: string
  time_format?: string
  measurement_system?: string
  visibility?: string
}

const TIMEZONES = [
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Singapore',
  'Europe/London',
  'America/New_York',
  'America/Los_Angeles',
  'Australia/Sydney',
  'UTC',
]
const CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'AED', 'SGD', 'AUD']
const COUNTRIES = ['IN', 'US', 'GB', 'AE', 'SG', 'AU', 'CA']
const LANGUAGES = ['en', 'hi', 'ta', 'te', 'kn', 'ml', 'mr', 'bn', 'gu']

/** Doc 09 CORE-016 Business Settings. */
export default async function SettingsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}`
  const res = await apiTry<{ data: Settings }>(`${base}/settings`, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Settings" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Settings" />
      </div>
    )
  }
  const settings = res.data.data || {}

  const prefsRes = await apiTry<{ data: Preferences }>(`${base}/preferences`, token)
  const preferences = prefsRes.ok ? prefsRes.data.data || {} : {}
  const businessBase = `/b/${params.businessId}`

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Business-wide configuration. Module settings live on each module's own page."
      />

      <section style={{ maxWidth: '32rem' }}>
        <h2 >Region and formats</h2>
        <form action={updateRegionalSettings} style={{ display: 'grid', gap: '0.6rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <label style={LABEL}>
            Timezone
            <select name="timezone" defaultValue={settings.timezone ?? 'Asia/Kolkata'} style={INPUT}>
              {TIMEZONES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label style={LABEL}>
            Currency
            <select name="currency" defaultValue={settings.currency ?? 'INR'} style={INPUT}>
              {CURRENCIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label style={LABEL}>
            Country
            <select name="country" defaultValue={settings.country ?? 'IN'} style={INPUT}>
              {COUNTRIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label style={LABEL}>
            Language
            <select name="language" defaultValue={settings.language ?? 'en'} style={INPUT}>
              {LANGUAGES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" style={BUTTON}>
            Save
          </button>
        </form>
      </section>

      <section style={{ marginTop: '2.25rem', maxWidth: '32rem' }}>
        <h2 >Display preferences</h2>
        <form action={updatePreferences} style={{ display: 'grid', gap: '0.6rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <label style={LABEL}>
            Date format
            <select
              name="date_format"
              defaultValue={preferences.date_format ?? 'DD/MM/YYYY'}
              style={INPUT}
            >
              {['DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD'].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label style={LABEL}>
            Time format
            <select name="time_format" defaultValue={preferences.time_format ?? '12h'} style={INPUT}>
              <option value="12h">12-hour</option>
              <option value="24h">24-hour</option>
            </select>
          </label>
          <label style={LABEL}>
            Measurements
            <select
              name="measurement_system"
              defaultValue={preferences.measurement_system ?? 'metric'}
              style={INPUT}
            >
              <option value="metric">Metric</option>
              <option value="imperial">Imperial</option>
            </select>
          </label>
          <button type="submit" style={BUTTON}>
            Save
          </button>
        </form>
      </section>

      <section style={{ marginTop: '2.25rem' }}>
        <h2 >Elsewhere</h2>
        <ul style={{ paddingLeft: '1.1rem', lineHeight: 1.9 }}>
          <li>
            <Link href={`${businessBase}/profile`}>Business profile</Link> — name, description,
            contact details
          </li>
          <li>
            <Link href={`${businessBase}/brand`}>Brand and media</Link>
          </li>
          <li>
            <Link href={`${businessBase}/team`}>Team and access</Link>
          </li>
          <li>
            <Link href={`${businessBase}/locations`}>Locations</Link>
          </li>
          <li>
            <Link href={`${businessBase}/modules`}>Modules</Link>
          </li>
          <li>
            <Link href={`${businessBase}/notifications`}>Notification preferences</Link>
          </li>
        </ul>
      </section>
    </div>
  )
}

const LABEL: React.CSSProperties = { display: 'grid', gap: '0.25rem', fontSize: '0.9rem' }
const INPUT: React.CSSProperties = {
  width: '100%',
}
const BUTTON: React.CSSProperties = {
  justifySelf: 'start',
}
