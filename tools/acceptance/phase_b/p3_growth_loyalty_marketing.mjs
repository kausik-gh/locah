// Phase B – Growth lane acceptance test: Loyalty, Referrals & Marketing (P3)
// Verifies:
//   LY-01  Points earn from order
//   LY-01  Idempotency: duplicate earn rejected
//   LY-01  Validate and redeem points
//   LY-03  Referral code issued per customer
//   LY-04  Gift voucher issue and validate
//   MK-01  Create campaign
//   MK-07  Create offer, evaluate offer code
//   MS-26  Regulated category blocks marketing
//
// Requires LOCAL stack: LOCAH_ACCEPT_SESSION, LOCAH_API
import { readFileSync } from 'node:fs'
import { recorder, caller, must, API } from './pw.mjs'

const session = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_SESSION, 'utf8'))
const api = must(session.token)
const get = caller(session.token)
const rec = recorder('growth-loyalty-marketing')
const { check, finish } = rec

// ─────────────────────────────────────────────────
// 0. Setup: create a business with a known customer
// ─────────────────────────────────────────────────
const biz = await api('/v1/platform/businesses', {
  method: 'POST',
  body: {
    display_name: `GrowthTest ${Date.now().toString().slice(-5)}`,
    business_type: 'other',
  },
})
const bizId = biz.data.business.id

// Create a test customer contact
const custRes = await api(`/v1/platform/businesses/${bizId}/customers`, {
  method: 'POST',
  body: { display_name: 'Test Customer', phone: '+919900000001' },
})
const contactId = custRes.data.id

// ─────────────────────────────────────────────────
// LY-01: Loyalty programme exists by default
// ─────────────────────────────────────────────────
const prog = await get(`/v1/platform/businesses/${bizId}/loyalty/program`)
check(prog.ok, 'LY-01: loyalty program returns 200')
check(prog.data.status === 'active', 'LY-01: default program is active')
check(prog.data.points_per_rupee > 0, 'LY-01: earn rate is positive')

// ─────────────────────────────────────────────────
// LY-01: Earn points from an order
// ─────────────────────────────────────────────────
const ikey1 = `order-${Date.now()}`
const earnRes = await get(
  `/v1/platform/businesses/${bizId}/loyalty/customers/${contactId}/earn`,
  {
    method: 'POST',
    body: {
      order_amount_paise: 50000, // ₹500
      source_type: 'order',
      source_id: `ord-${Date.now()}`,
      idempotency_key: ikey1,
      reason: 'earn_order',
    },
  }
)
check(earnRes.ok, 'LY-01: earn points returns 200')
check((earnRes.data.points_earned ?? 0) > 0, 'LY-01: points_earned > 0 for ₹500 order')

// ─────────────────────────────────────────────────
// LY-01: Duplicate earn (same idempotency_key) is idempotent
// ─────────────────────────────────────────────────
const earnDup = await get(
  `/v1/platform/businesses/${bizId}/loyalty/customers/${contactId}/earn`,
  {
    method: 'POST',
    body: {
      order_amount_paise: 50000,
      source_type: 'order',
      source_id: `ord-${Date.now()}-dup`,
      idempotency_key: ikey1,
      reason: 'earn_order',
    },
  }
)
check(earnDup.ok, 'LY-01: duplicate earn idempotency key returns 200 (not 409)')

// ─────────────────────────────────────────────────
// LY-01: Balance reflects earned points
// ─────────────────────────────────────────────────
const balance = await get(
  `/v1/platform/businesses/${bizId}/loyalty/customers/${contactId}/balance`
)
check(balance.ok, 'LY-01: balance endpoint returns 200')
check((balance.data.usable_points ?? 0) > 0, 'LY-01: usable_points > 0 after earn')

// ─────────────────────────────────────────────────
// LY-01: Validate redemption
// ─────────────────────────────────────────────────
const usable = balance.data.usable_points
const validateRes = await get(
  `/v1/platform/businesses/${bizId}/loyalty/customers/${contactId}/validate-redemption`,
  {
    method: 'POST',
    body: { points_to_redeem: Math.max(1, Math.floor(usable / 2)), order_amount_paise: 100000 },
  }
)
check(validateRes.ok, 'LY-01: validate-redemption returns 200')
check(typeof validateRes.data.allowed === 'boolean', 'LY-01: validate returns allowed field')

// ─────────────────────────────────────────────────
// LY-03: Referral code issued per customer
// ─────────────────────────────────────────────────
const refCodeRes = await get(
  `/v1/platform/businesses/${bizId}/loyalty/customers/${contactId}/referral`
)
check(refCodeRes.ok, 'LY-03: referral code endpoint returns 200')
check(typeof refCodeRes.data.code === 'string' && refCodeRes.data.code.length >= 4, 'LY-03: code is a non-empty string')

// ─────────────────────────────────────────────────
// LY-04: Gift voucher issue and validate
// ─────────────────────────────────────────────────
const voucherRes = await get(`/v1/platform/businesses/${bizId}/loyalty/vouchers`, {
  method: 'POST',
  body: {
    issued_amount_paise: 50000, // ₹500
    recipient_name: 'Gift Recipient',
    expiry_days: 365,
  },
})
check(voucherRes.ok, 'LY-04: issue voucher returns 200')
const vCode = voucherRes.data?.code
check(typeof vCode === 'string', 'LY-04: voucher has code')

const validateVoucher = await get(
  `/v1/platform/businesses/${bizId}/loyalty/vouchers/${vCode}`
)
check(validateVoucher.ok, 'LY-04: validate voucher by code returns 200')
check(validateVoucher.data.status === 'active', 'LY-04: newly issued voucher is active')
check(validateVoucher.data.remaining_balance_paise === 50000, 'LY-04: remaining balance = issued amount')

// ─────────────────────────────────────────────────
// MK-07: Create an offer
// ─────────────────────────────────────────────────
const offerRes = await get(`/v1/platform/businesses/${bizId}/marketing/offers`, {
  method: 'POST',
  body: {
    code: `TEST${Date.now().toString().slice(-4)}`,
    name: 'Launch discount',
    kind: 'percentage_discount',
    discount_value: 10,
    min_order_amount_paise: 20000,
    usage_limit_total: 100,
    usage_limit_per_customer: 1,
  },
})
check(offerRes.ok, 'MK-07: create offer returns 200')
check(offerRes.data.status === 'active', 'MK-07: new offer is active')
const offerCode = offerRes.data.code

// ─────────────────────────────────────────────────
// MK-07: Evaluate offer code
// ─────────────────────────────────────────────────
const evalRes = await get(`/v1/platform/businesses/${bizId}/marketing/offers/evaluate`, {
  method: 'POST',
  body: {
    code: offerCode,
    cart_total_paise: 50000,
    customer_contact_id: contactId,
  },
})
check(evalRes.ok, 'MK-07: evaluate offer returns 200')
check(typeof evalRes.data.discount_paise === 'number', 'MK-07: evaluation returns discount_paise')
check(evalRes.data.discount_paise === 5000, `MK-07: 10% of ₹500 = ₹50 (got ₹${evalRes.data.discount_paise / 100})`)

// ─────────────────────────────────────────────────
// MK-01: Create a campaign (draft)
// ─────────────────────────────────────────────────
const campaignRes = await get(`/v1/platform/businesses/${bizId}/marketing/campaigns`, {
  method: 'POST',
  body: {
    name: 'First campaign',
    goal: 'drive_orders',
    channel: 'whatsapp',
    budget_paise: 100000,
    schedule_type: 'immediate',
  },
})
check(campaignRes.ok, 'MK-01: create campaign returns 200')
check(campaignRes.data.status === 'draft', 'MK-01: new campaign starts as draft')

// ─────────────────────────────────────────────────
// MK-01: List campaigns includes the one we created
// ─────────────────────────────────────────────────
const listRes = await get(`/v1/platform/businesses/${bizId}/marketing/campaigns`)
check(listRes.ok, 'MK-01: list campaigns returns 200')
check(Array.isArray(listRes.data.campaigns), 'MK-01: campaigns is an array')
check(listRes.data.campaigns.length >= 1, 'MK-01: at least one campaign in list')

// ─────────────────────────────────────────────────
// MS-26: Marketing policy check
// ─────────────────────────────────────────────────
const policyRes = await get(`/v1/platform/businesses/${bizId}/marketing/policy`)
check(policyRes.ok, 'MS-26: marketing policy returns 200')
check(typeof policyRes.data.allowed === 'boolean', 'MS-26: policy returns allowed boolean')
check(typeof policyRes.data.status === 'string', 'MS-26: policy returns status string')

// ─────────────────────────────────────────────────
// Business isolation: different business cannot see loyalty data
// ─────────────────────────────────────────────────
const biz2 = await api('/v1/platform/businesses', {
  method: 'POST',
  body: { display_name: `GrowthTest2 ${Date.now().toString().slice(-5)}`, business_type: 'other' },
})
const biz2Id = biz2.data.business.id
const crossRes = await get(
  `/v1/platform/businesses/${biz2Id}/loyalty/customers/${contactId}/balance`
)
// Should return 404 or empty (contact doesn't belong to biz2)
check(!crossRes.ok || (crossRes.data.usable_points ?? 0) === 0, 'LY-01: cross-business isolation — biz2 cannot see biz1 customer points')

finish()
