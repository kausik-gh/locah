import type { Metadata } from 'next'
import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { REFERENCE_MODELS } from '@/lib/product-catalogue'

export const metadata: Metadata = {
  title: 'For businesses — LOCAH',
  description:
    'Take your local business digital: a real website, a listing customers can find, and working orders, bookings and payments — set up in an afternoon.',
}

const OBJECTIONS = [
  {
    q: 'I am not technical.',
    a: 'You will not see a schema, a template language or a line of code. Setup is a short conversation about your business, and editing is clicking the words on your own page and changing them.',
  },
  {
    q: 'I already have a page on social media.',
    a: 'Keep it. What you do not have is a place customers can browse what you sell and actually order it — and a record of that order you can work from tomorrow morning.',
  },
  {
    q: 'I do not want to learn five tools.',
    a: 'That is the point. Your website, your listing, your catalogue, your orders and your customers are the same system, so they never disagree with each other.',
  },
  {
    q: 'What if my business does not fit a template?',
    a: 'LOCAH models eleven kinds of local business, and adapts the site, the checkout and the Workspace to the one you pick. If something genuinely does not fit, the AI layer structures it rather than forcing you into the wrong shape.',
  },
]

export default function ForBusinessesPage() {
  return (
    <div className="locah-public">
      <PublicNav active="business" />
      <main>
        <section className="lc-section lc-ground-paper">
          <div className="lc-container lc-container--wide">
            <div className="lc-split">
              <div>
                <p className="lc-eyebrow">For business owners</p>
                <h1 className="lc-display">
                  Ready to take your business <span className="lc-mark">digital</span>?
                </h1>
                <p className="lc-lead">
                  You do not need a developer, a designer and three subscriptions. Tell LOCAH what
                  you do, and you leave with a website customers can buy from and a place to run
                  the work that comes back.
                </p>
                <div className="lc-row" style={{ marginTop: 'var(--sp-6)' }}>
                  <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                    Set up your business
                  </Link>
                  <Link className="lc-btn lc-btn--ghost lc-btn--lg" href="/capabilities">
                    See the capabilities
                  </Link>
                </div>
                <p className="lc-small lc-muted" style={{ marginTop: 'var(--sp-4)' }}>
                  Nothing goes public until you press publish.
                </p>
              </div>

              <ol className="lc-steps">
                <li className="lc-step">
                  <div>
                    <p className="lc-step__title">Tell us what you do</p>
                    <p className="lc-step__body">
                      Pick your business type. The questions that follow change to match it — a
                      café is asked about its menu, a salon about its services and staff.
                    </p>
                  </div>
                </li>
                <li className="lc-step">
                  <div>
                    <p className="lc-step__title">LOCAH builds the site</p>
                    <p className="lc-step__body">
                      Pages, sections, copy and a theme that suits your trade — generated as
                      structured content, so every part of it stays editable.
                    </p>
                  </div>
                </li>
                <li className="lc-step">
                  <div>
                    <p className="lc-step__title">Edit and publish</p>
                    <p className="lc-step__body">
                      Change any wording or image, add what you sell, preview the result, and go
                      live when it reads the way you want.
                    </p>
                  </div>
                </li>
                <li className="lc-step">
                  <div>
                    <p className="lc-step__title">Run it from one place</p>
                    <p className="lc-step__body">
                      Orders and bookings arrive in your Workspace alongside your customers,
                      payments and stock.
                    </p>
                  </div>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section className="lc-section lc-ground-cream">
          <div className="lc-container lc-container--wide">
            <div className="lc-center" style={{ marginBottom: 'var(--sp-8)' }}>
              <p className="lc-eyebrow">Eleven kinds of local business</p>
              <h2>LOCAH already knows how your trade works.</h2>
              <p className="lc-lead" style={{ marginInline: 'auto' }}>
                Each of these has its own path from discovery to payment — and its own set of
                modules. Pick yours and the whole product rearranges around it.
              </p>
            </div>

            <div className="lc-grid lc-grid--2">
              {REFERENCE_MODELS.map((m) => (
                <article className="lc-card" key={m.name}>
                  <h3 className="lc-card__title">{m.name}</h3>
                  <p className="lc-small lc-muted" style={{ marginBottom: 'var(--sp-3)' }}>
                    {m.examples}
                  </p>
                  <p className="lc-card__body" style={{ marginBottom: 'var(--sp-4)' }}>
                    {m.path}
                  </p>
                  <div className="lc-row" style={{ gap: 'var(--sp-2)' }}>
                    {m.modules.map((mod) => (
                      <span className="lc-badge" key={mod}>
                        {mod}
                      </span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="lc-section">
          <div className="lc-container lc-container--wide">
            <div className="lc-center" style={{ marginBottom: 'var(--sp-8)' }}>
              <p className="lc-eyebrow">Straight answers</p>
              <h2>The things owners actually ask.</h2>
            </div>
            <div className="lc-grid lc-grid--2">
              {OBJECTIONS.map((o) => (
                <article className="lc-card" key={o.q}>
                  <h3 className="lc-card__title">{o.q}</h3>
                  <p className="lc-card__body">{o.a}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="lc-section lc-ground-ink">
          <div className="lc-container">
            <div className="lc-center">
              <h2>Your business, online by this evening.</h2>
              <p className="lc-lead" style={{ marginInline: 'auto' }}>
                Setup takes a few minutes. Publishing takes one click. You can change anything
                afterwards.
              </p>
              <div className="lc-row lc-row--center" style={{ marginTop: 'var(--sp-6)' }}>
                <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                  Set up your business
                </Link>
                <Link className="lc-btn lc-btn--ghost lc-btn--lg" href="/marketplace">
                  See businesses already on LOCAH
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}
