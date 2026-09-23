import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchPublicWebsite, websiteMetadata } from '@/lib/public-website'
import { WebsitePageView } from '@/components/website/WebsitePageView'

export const revalidate = 60

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: { slug: string; pageSlug: string }
  searchParams?: { preview_token?: string }
}): Promise<Metadata> {
  if (RESERVED_SLUGS.has(params.slug)) return {}
  // See the home route: a preview of an unlisted draft needs the token here
  // as well, or the tab title falls back to LOCAH's.
  return websiteMetadata(
    await fetchPublicWebsite(params.slug, params.pageSlug, searchParams?.preview_token)
  )
}

export default async function BusinessWebsitePage({
  params,
  searchParams,
}: {
  params: { slug: string; pageSlug: string }
  searchParams?: { preview_token?: string }
}) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const data = await fetchPublicWebsite(params.slug, params.pageSlug, searchParams?.preview_token)
  if (!data) notFound()
  return (
    <WebsitePageView
      data={data}
      previewToken={data.is_preview ? searchParams?.preview_token : undefined}
    />
  )
}
