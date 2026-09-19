import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'

/**
 * The public app's own 404.
 *
 * Without this the platform answered an unknown address with Next's built-in
 * page — unstyled, wordless, and carrying no way back. It is the page a mistyped
 * Business address lands on, so it is also the first thing some visitors ever
 * see of LOCAH.
 */
export default function NotFound() {
  return (
    <div className="locah-public">
      <PublicNav />
      <main className="lc-container" style={{ paddingBlock: '5rem 6rem', maxWidth: '38rem' }}>
        <p className="lc-eyebrow">Not found</p>
        <h1 style={{ fontSize: '2.1rem', margin: '0.4rem 0 0.8rem' }}>
          There is nothing at this address
        </h1>
        <p className="lc-lead" style={{ margin: 0 }}>
          The page may have moved, or the business you are looking for may not be listed. Search
          the Marketplace and you will probably find them.
        </p>
        <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', marginTop: '1.8rem' }}>
          <Link href="/marketplace" className="lc-btn lc-btn--primary">
            Search the Marketplace
          </Link>
          <Link href="/" className="lc-btn lc-btn--ghost">
            Go to the home page
          </Link>
        </div>
      </main>
      <PublicFooter />
    </div>
  )
}
