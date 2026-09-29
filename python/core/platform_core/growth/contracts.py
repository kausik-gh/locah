"""Claude integration hooks for growth.

These names are the only seam. Do not call Orders, Payments or Messaging
from Loyalty or Marketing, and do not edit those modules to earn points,
qualify a referral, validate a coupon, send a broadcast, or fund a voucher.
The owning lane calls the function below when its own event is final.
"""

from __future__ import annotations

# Eligible completed transaction (order, counter bill) -> points exactly once.
# Caller: Orders / POS, after the sale is completed and paid as that lane defines.
# Hook: LoyaltyPointsService.earn_points
#   idempotency_key must be stable for that sale (for example "order:{order_id}").
#   source_type is "order" or "pos". source_id is that sale's id.
LOYALTY_EARN_FROM_COMPLETED_TRANSACTION = (
    "platform_core.loyalty.service.LoyaltyPointsService.earn_points"
)

# The friend's first eligible purchase -> referral reward exactly once.
# Caller: Orders, when that contact's first completed sale is recorded.
# Hook: ReferralService.qualify_first_purchase
#   A second call for the same referee returns qualified=False.
LOYALTY_REFERRAL_ON_FIRST_PURCHASE = (
    "platform_core.loyalty.service.ReferralService.qualify_first_purchase"
)

# Coupon validation at checkout. Does not redeem stock or money.
# Caller: Checkout / Orders, before the total is accepted.
# Hook: OfferService.evaluate_offer
MARKETING_COUPON_AT_CHECKOUT = "platform_core.marketing.offers.OfferService.evaluate_offer"

# An approved broadcast is ready for Messaging to deliver.
# Caller: Messaging, later. Dispatch here records recipients and consent
# exclusions against a fixture transport. It does not call Meta or WhatsApp.
# Hook: WhatsAppBroadcastOrchestrator.dispatch_campaign
#   Campaign status must already be APPROVED by someone holding marketing.approve.
MARKETING_APPROVED_BROADCAST = (
    "platform_core.marketing.broadcast.WhatsAppBroadcastOrchestrator.dispatch_campaign"
)

# Buying or funding a gift voucher is a payment. This lane only records the
# balance after that payment exists.
# Caller: Payments, after the voucher purchase is captured.
# Hook: GiftVoucherService.issue_voucher
LOYALTY_VOUCHER_AFTER_PAYMENT = "platform_core.loyalty.service.GiftVoucherService.issue_voucher"
