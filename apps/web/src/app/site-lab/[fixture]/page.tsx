import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { notFound } from 'next/navigation'
import { WebsitePageView } from '@/components/website/WebsitePageView'
import type { PublicWebsitePayload } from '@/lib/public-website'

export const dynamic = 'force-dynamic'
export const metadata = { robots: { index: false, follow: false } }

/**
 * The site lab: a website fixture rendered by the real tenant renderer.
 *
 * Local only. It exists when LOCAH_SITE_LAB_DIR points at fixtures written by
 * `platform_testing.website_fixtures` and is a 404 everywhere else — no
 * database, no API, no business data, nothing to reach in production.
 */
export default async function SiteLabPage({ params }: { params: { fixture: string } }) {
  const dir = process.env.LOCAH_SITE_LAB_DIR
  if (!dir || !/^[a-z0-9-]{2,40}$/.test(params.fixture)) notFound()
  let data: PublicWebsitePayload
  try {
    data = JSON.parse(await readFile(path.join(dir, `${params.fixture}.json`), 'utf8'))
  } catch {
    notFound()
  }
  return <WebsitePageView data={data} />
}
