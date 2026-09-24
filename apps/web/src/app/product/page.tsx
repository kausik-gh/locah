import type { Metadata } from 'next'
import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'

export const metadata: Metadata = {
  title: 'The product — LOCAH',
  description: 'From the first conversation to the work of running a business, see how LOCAH connects your website, discovery and operations.',
}

const STAGES = [
  { number: '01', name: 'Understand', line: 'Begin with the business, not a template.', copy: 'Describe what you do in your own words. LOCAH organises the facts about your business so the next steps reflect how you actually work.', detail: 'Business interview · structured business profile' },
  { number: '02', name: 'Set up', line: 'One source of truth. Many useful places.', copy: 'Your business profile, offerings and brand give your website and Marketplace listing a shared foundation. Review everything before it goes live.', detail: 'Website · profile · catalogue' },
  { number: '03', name: 'Connect', line: 'Be discoverable, then be ready to respond.', copy: 'Customers can discover your business and reach the actions you enable. Orders, bookings or enquiries flow into the same Workspace you use every day.', detail: 'Marketplace · orders · bookings · leads' },
  { number: '04', name: 'Operate', line: 'The work stays close to the business.', copy: 'See what needs attention, work through the day and keep the details current. Turn on the relevant modules; leave the rest out of the way.', detail: 'Workspace · team · modules' },
] as const

export default function ProductPage() {
  return <div className="locah-public">
    <PublicNav active="product" />
    <main>
      <section className="ui-editorial-hero">
        <div className="lc-container lc-container--wide ui-editorial-hero__grid">
          <div>
            <p className="lc-eyebrow">One connected business</p>
            <h1 className="ui-display">Not another website builder. <em>A place to run what comes next.</em></h1>
          </div>
          <div className="ui-editorial-hero__aside">
            <p>LOCAH starts by understanding your business. From there, your presence, discovery and day-to-day tools work from the same information.</p>
            <Link className="lc-btn lc-btn--primary" href="/start">Start with your business <span aria-hidden="true">↗</span></Link>
          </div>
        </div>
        <div className="lc-container lc-container--wide ui-signal-line" aria-label="The LOCAH journey">
          <span>Tell us</span><span>Shape it</span><span>Go live</span><span>Run it</span>
        </div>
      </section>

      <section className="ui-life-section lc-container lc-container--wide" aria-labelledby="lifecycle-title">
        <div className="ui-section-intro"><p className="lc-eyebrow">The whole picture</p><h2 id="lifecycle-title">A business is a living system.</h2><p>LOCAH keeps its moving parts connected without making you manage the connections.</p></div>
        <div className="ui-life-list">{STAGES.map(stage => <article className="ui-life-row" key={stage.number}>
          <span className="ui-life-row__number">{stage.number}</span>
          <div><p className="ui-life-row__name">{stage.name}</p><h3>{stage.line}</h3><p>{stage.copy}</p></div>
          <span className="ui-life-row__detail">{stage.detail}</span>
        </article>)}</div>
      </section>

      <section className="ui-dark-panel"><div className="lc-container lc-container--wide ui-dark-panel__grid">
        <div><p className="lc-eyebrow">A better starting point</p><h2>Tell LOCAH what makes your business yours.</h2></div>
        <div><p>We translate your answers into an editable business foundation. You stay in control of the facts, your website and when to publish.</p><Link className="lc-btn lc-btn--primary" href="/how-it-works">See the process</Link></div>
      </div></section>
    </main><PublicFooter />
  </div>
}
