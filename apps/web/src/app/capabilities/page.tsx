import type { Metadata } from 'next'
import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import {
  CORE_MODULES,
  LAUNCH_MODULES,
  ROADMAP_MODULES,
  type Module,
} from '@/lib/product-catalogue'

export const metadata: Metadata = {
  title: 'Capabilities — LOCAH',
  description:
    'Every capability LOCAH gives a local business: what is always on, what you can switch on, and what is still on the roadmap.',
}

function ModuleGrid({ modules, tone }: { modules: Module[]; tone?: 'muted' }) {
  return (
    <div className="lc-grid lc-grid--3">
      {modules.map((m) => (
        <article className="lc-card" key={m.id} style={tone === 'muted' ? { opacity: 0.86 } : undefined}>
          <h3 className="lc-card__title">{m.name}</h3>
          <p className="lc-card__body">{m.blurb}</p>
        </article>
      ))}
    </div>
  )
}

export default function CapabilitiesPage() {
  return (
    <div className="locah-public">
      <PublicNav active="capabilities" />
      <main>
        <section className="lc-section lc-ground-paper">
          <div className="lc-container lc-container--wide">
            <p className="lc-eyebrow">Capabilities</p>
            <h1 className="lc-display" style={{ maxWidth: '20ch' }}>
              Switch on only what your business <span className="lc-mark">actually needs</span>.
            </h1>
            <p className="lc-lead">
              LOCAH is built as modules. Some are part of every business from the moment you sign
              up. The rest you turn on when you need them — so a consultant is never asked to think
              about stock levels, and a café is never buried in a CRM.
            </p>
            <div className="lc-row" style={{ marginTop: 'var(--sp-6)' }}>
              <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                Set up your business
              </Link>
            </div>
          </div>
        </section>

        <section className="lc-section">
          <div className="lc-container lc-container--wide">
            <p className="lc-eyebrow">Always on</p>
            <h2>The foundation every business gets.</h2>
            <p className="lc-lead" style={{ marginBottom: 'var(--sp-7)' }}>
              Granted automatically. You never choose these, and you cannot break them by turning
              something else off.
            </p>
            <ModuleGrid modules={CORE_MODULES} />
          </div>
        </section>

        <section className="lc-section lc-ground-cream">
          <div className="lc-container lc-container--wide">
            <p className="lc-eyebrow">Available now</p>
            <h2>The operating modules.</h2>
            <p className="lc-lead" style={{ marginBottom: 'var(--sp-7)' }}>
              Available at launch. LOCAH suggests the right set for your business type during
              setup, and you can change your mind at any time from your Workspace.
            </p>
            <ModuleGrid modules={LAUNCH_MODULES} />
          </div>
        </section>

        <section className="lc-section">
          <div className="lc-container lc-container--wide">
            <p className="lc-eyebrow">On the roadmap</p>
            <h2>Defined, not yet available.</h2>
            <p className="lc-lead" style={{ marginBottom: 'var(--sp-7)' }}>
              These are real parts of the LOCAH model with a place already reserved for them. They
              are not switchable yet, and we would rather tell you that than pretend otherwise.
            </p>
            <ModuleGrid modules={ROADMAP_MODULES} tone="muted" />
          </div>
        </section>

        <section className="lc-section lc-ground-ink">
          <div className="lc-container">
            <div className="lc-center">
              <h2>Not sure which you need?</h2>
              <p className="lc-lead" style={{ marginInline: 'auto' }}>
                Tell LOCAH what kind of business you run and it will recommend a starting set — and
                explain why each one is there.
              </p>
              <div className="lc-row lc-row--center" style={{ marginTop: 'var(--sp-6)' }}>
                <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                  Get started
                </Link>
                <Link className="lc-btn lc-btn--ghost lc-btn--lg" href="/for-businesses">
                  How LOCAH works
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
