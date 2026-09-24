import { redirect } from 'next/navigation'

/** The Stage 3 search page moved into the Marketplace; old links keep working. */
export default function LegacySearchPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>
}) {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(searchParams || {})) {
    if (Array.isArray(value)) value.forEach((v) => qs.append(key, v))
    else if (value) qs.set(key, value)
  }
  const s = qs.toString()
  redirect(s ? `/marketplace/search?${s}` : '/marketplace/search')
}
