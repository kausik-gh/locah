import type { Metadata } from 'next'
import { PolicyPage, type PolicySection } from '@/components/public/PolicyPage'
import { MERCHANT } from '@/lib/merchant-details'

export const metadata: Metadata = { title: 'Shipping & Digital Delivery Policy — LOCAH', description: 'How LOCAH delivers software access, website creation and other digital services.' }

const sections: PolicySection[] = [
  { id: 'physical-shipping', title: 'Physical shipping', content: <><p>LOCAH sells software and digital business services through its own website. We do not currently sell or ship physical goods from the LOCAH corporate website. There is no LOCAH courier charge or physical shipping address requirement for a LOCAH subscription or digital service.</p><p>Individual businesses using LOCAH may sell physical goods on their own sites. Their fulfilment and shipping terms are set by those businesses and are separate from this policy.</p></> },
  { id: 'digital-delivery', title: 'Digital delivery', content: <p>When a paid LOCAH purchase is accepted and payment is confirmed, the purchased service is delivered electronically through the customer’s LOCAH account. Depending on the purchase, delivery may mean activating a billing period, creating or publishing a business website, providing Workspace access, or another digital service described before payment.</p> },
  { id: 'timing', title: 'Delivery timing', content: <><p>Account and subscription access is normally activated shortly after a successful payment is confirmed. AI-generated websites and other generated outputs can take additional processing time.</p><p>Where technically available, LOCAH shows progress or status in the application. We will communicate material delays or delivery issues through the contact details associated with the account.</p></> },
  { id: 'delivery-problems', title: 'Delivery problems', content: <p>If you have made a successful payment but your service has not been activated, email <a href={`mailto:${MERCHANT.email}`}>{MERCHANT.email}</a> or call <a href={MERCHANT.phoneHref}>{MERCHANT.phone}</a>. Include the payment reference and your LOCAH account details. Our <a href="/refunds">Refund & Cancellation Policy</a> explains what happens when delivery cannot be completed.</p> },
]

export default function DeliveryPage() {
  return <PolicyPage eyebrow="Digital service delivery" title="Shipping & Digital Delivery Policy" intro="LOCAH’s own services are delivered online. Here is what to expect after purchase." sections={sections} current="/delivery" />
}
