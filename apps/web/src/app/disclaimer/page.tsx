import type { Metadata } from 'next'
import Link from 'next/link'
import { PolicyPage, type PolicySection } from '@/components/public/PolicyPage'

export const metadata: Metadata = { title: 'Disclaimer — LOCAH', description: 'Important information about AI-assisted content, third-party services, business listings and platform availability.' }

const sections: PolicySection[] = [
  { id: 'ai-content', title: 'AI-assisted content', content: <p>LOCAH may help organize business facts, draft copy and create website content with AI. Generated material can be incomplete or incorrect. Review names, prices, claims, images, contact information and legal statements before publishing or relying on them.</p> },
  { id: 'business-content', title: 'Business listings and websites', content: <p>Businesses using LOCAH provide and approve their own information and offerings. LOCAH does not independently certify every listing, price, availability, licence or claim. A customer should confirm important details directly with the business before purchasing or booking.</p> },
  { id: 'third-party', title: 'Third-party providers', content: <p>Payment gateways, messaging services, maps, AI providers and other connected services may operate under separate terms and may experience interruptions. Their charges, if applicable, are separate from LOCAH’s platform charges unless the purchase description states otherwise.</p> },
  { id: 'availability', title: 'Service availability', content: <p>We work to keep LOCAH available and accurate, but maintenance, network problems and provider outages can interrupt access. Some features are available only after they are enabled for a particular account. The <Link href="/pricing">Pricing page</Link> explains current public offers; it does not promise access to future modules.</p> },
  { id: 'payment-boundary', title: 'Who receives a payment', content: <p>Payments for LOCAH’s own software and digital services are separate from payments to an independent business for goods or services sold on that business’s site. For a merchant purchase, consult that business’s checkout details and policies. For a LOCAH service purchase, our <Link href="/terms">Terms</Link> and <Link href="/refunds">Refund & Cancellation Policy</Link> apply.</p> },
]

export default function DisclaimerPage() {
  return <PolicyPage eyebrow="Important information" title="Disclaimer" intro="What LOCAH can help with, and where you should review details before acting." sections={sections} current="/disclaimer" />
}
