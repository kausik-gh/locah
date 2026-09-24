import { getAccessToken } from '@/lib/supabase/access-token'
import { listMyBusinesses, type BusinessSummary } from '@/lib/platform-api'
import { fetchDiscover, type Listing } from '@/lib/marketplace-api'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import {
  ClosingCta,
  ConnectedBento,
  ConversationToSystem,
  Hero,
  HowItWorks,
  LiveMarketplace,
  ModuleEcosystem,
  PricingPreview,
  WhatItBecomes,
  WhyDifferent,
} from '@/components/home/HomeSections'
import { platformUrl } from '@platform/config'
import './home.css'

export const dynamic = 'force-dynamic'

const WORKSPACE_URL = platformUrl('workspace')

export default async function HomePage() {
  const token = await getAccessToken()

  // Both are best-effort: the front door must render even if the API is down.
  const [businesses, discover] = await Promise.all([
    token
      ? listMyBusinesses(token)
          .then((bs) => bs.filter((b) => b.state !== 'closed'))
          .catch(() => [] as BusinessSummary[])
      : Promise.resolve([] as BusinessSummary[]),
    fetchDiscover({}).catch(() => null),
  ])

  // The newest published listings are the honest preview: no ranking by a
  // popularity LOCAH does not measure.
  const recent: Listing[] = discover?.rails.find((r) => r.id === 'new')?.items ?? []
  const first = businesses[0]

  return (
    <div className="locah-public">
      <PublicNav signedIn={Boolean(token)} businesses={businesses} />
      <main>
        <Hero
          workspaceHref={first ? `${WORKSPACE_URL}/b/${first.id}` : undefined}
          businessName={first?.display_name}
        />
        <ConversationToSystem />
        <ConnectedBento />
        <HowItWorks />
        <LiveMarketplace listings={recent} total={discover?.totals.businesses ?? recent.length} />
        <WhatItBecomes />
        <ModuleEcosystem />
        <WhyDifferent />
        <PricingPreview />
        <ClosingCta signedIn={Boolean(token)} />
      </main>
      <PublicFooter />
    </div>
  )
}
