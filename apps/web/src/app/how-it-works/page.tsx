import type { Metadata } from 'next'
import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'

export const metadata: Metadata = {
  title: 'How it works — LOCAH',
  description: 'A clear route from describing your business to reviewing your website and running the day from one Workspace.',
}

const STEPS = [
  { n: '01', title: 'Tell us about your business', body: 'Start with your name and describe what you do. The interview follows your business, not a generic industry checklist.', note: 'A conversation, not a configuration maze.' },
  { n: '02', title: 'Review what LOCAH understood', body: 'Check the business facts before they become your digital presence. Correct an answer or add detail when something is missing.', note: 'Your facts stay yours to edit.' },
  { n: '03', title: 'Choose the tools that fit', body: 'See which operating modules are useful for your business. Keep the setup focused; you can return to modules from Workspace.', note: 'Only relevant tools enter the picture.' },
  { n: '04', title: 'Make your presence yours', body: 'Review the website and the information customers will see. Add offerings, adjust content and publish only when you are ready.', note: 'Preview first. Publish deliberately.' },
  { n: '05', title: 'Run the day in Workspace', body: 'Your website, discovery and operating tools share the same business foundation. New work comes back to one place.', note: 'One business, one working context.' },
] as const

export default function HowItWorksPage() {
  return <div className="locah-public">
    <PublicNav active="how" />
    <main>
      <section className="ui-editorial-hero ui-editorial-hero--cream"><div className="lc-container lc-container--wide ui-editorial-hero__grid">
        <div><p className="lc-eyebrow">From idea to everyday</p><h1 className="ui-display">Start with a conversation. <em>End with a business that works.</em></h1></div>
        <div className="ui-editorial-hero__aside"><p>Five clear steps. You can review and change the important details at every point.</p><Link className="lc-btn lc-btn--primary" href="/start">Add your business <span aria-hidden="true">↗</span></Link></div>
      </div></section>
      <section className="lc-container lc-container--wide ui-process" aria-label="Setup steps">
        {STEPS.map(step => <article className="ui-process__step" key={step.n}>
          <span className="ui-process__number">{step.n}</span>
          <div><h2>{step.title}</h2><p>{step.body}</p></div>
          <span className="ui-process__note">{step.note}</span>
        </article>)}
      </section>
      <section className="ui-dark-panel"><div className="lc-container lc-container--wide ui-dark-panel__grid"><h2>Your business is the starting point. Everything else follows.</h2><div><p>Have a name and a rough description? That is enough to begin.</p><Link className="lc-btn lc-btn--primary" href="/start">Get started</Link></div></div></section>
    </main><PublicFooter />
  </div>
}
