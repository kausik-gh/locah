import type { Metadata } from 'next'
import Link from 'next/link'
import { fetchCategories, type TaxonomyFamily } from '@/lib/marketplace-api'
import { getNavAccount } from '@/lib/nav-account'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { CategoryIndex } from '@/components/marketplace/CategoryIndex'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'All categories — LOCAH Marketplace',
  description: 'Every kind of business on the LOCAH Marketplace, with how many are listed in each.',
}

export default async function CategoriesPage() {
  const [families, account] = await Promise.all([
    fetchCategories().catch(() => [] as TaxonomyFamily[]),
    getNavAccount(),
  ])
  const listed = families.reduce((n, f) => n + f.count, 0)
  return (
    <div className="locah-public">
      <PublicNav active="marketplace" signedIn={account.signedIn} businesses={account.businesses} />
      <main className="mx-page">
        <div className="lc-container lc-container--wide mx-cathead">
          <nav className="mx-crumbs" aria-label="Breadcrumb">
            <Link href="/marketplace">Marketplace</Link>
            <span aria-hidden="true">/</span>
            <span aria-current="page">All categories</span>
          </nav>
          <h1 className="mx-results__h1">Every kind of business</h1>
          <p className="mx-results__intro">
            {families.length} families and{' '}
            {families.reduce((n, f) => n + f.categories.length, 0)} categories. Every number is a count
            of real listings{listed > 0 ? '' : ', and the Marketplace is just getting started'}.
          </p>
        </div>
        <div className="lc-container lc-container--wide">
          {families.length > 0 ? (
            <CategoryIndex families={families} />
          ) : (
            <div className="mx-empty">
              <p className="mx-empty__title">Categories could not be loaded right now.</p>
              <p>Please try again in a moment.</p>
            </div>
          )}
        </div>
      </main>
      <PublicFooter />
    </div>
  )
}
