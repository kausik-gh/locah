"""The words each kind of recurring relationship uses (Founder refinement §1, §22–§23).

One engine underneath; a milk customer reads "My Subscription", a gym member
"My Membership", a parent "Fees", an AC owner "My Service Plan", a club member
"Dues". Owners see the home their trade expects.
"""

from __future__ import annotations

KIND_WORDS: dict[str, dict[str, str]] = {
    "access": {
        "kind_label": "Membership", "noun": "membership", "people": "Members", "customer_title": "My Membership",
        "owner_home": "Members", "renew": "Renew membership", "valid": "Valid until",
    },
    "session_pack": {
        "kind_label": "Session pack", "noun": "session pack", "people": "Clients", "customer_title": "My Sessions",
        "owner_home": "Session packs", "renew": "Buy another pack", "valid": "Use by",
    },
    "recurring_delivery": {
        "kind_label": "Subscription", "noun": "subscription", "people": "Subscribers",
        "customer_title": "My Subscription", "owner_home": "Subscriptions", "renew": "Renew subscription",
        "valid": "Paid until",
    },
    "service_contract": {
        "kind_label": "Service contract", "noun": "service plan", "people": "Contracts",
        "customer_title": "My Service Plan", "owner_home": "Contracts", "renew": "Renew contract",
        "valid": "Covered until",
    },
    "fee_plan": {
        "kind_label": "Fee plan", "noun": "fee plan", "people": "Students", "customer_title": "Fees & Enrolment",
        "owner_home": "Fees", "renew": "Enrol for the next term", "valid": "Term ends",
    },
    "member_dues": {
        "kind_label": "Member dues", "noun": "membership", "people": "Members", "customer_title": "My Membership",
        "owner_home": "Members & dues", "renew": "Pay dues", "valid": "Dues paid through",
    },
}

STATUS_WORDS: dict[str, str] = {
    "pending": "Payment pending",
    "active": "Active",
    "paused": "Paused",
    "grace": "In grace",
    "expired": "Expired",
    "cancelled": "Cancelled",
    "completed": "Completed",
}

# What the front desk sees on a check-in (Founder §6: green / amber / red).
CHECKIN_COLOURS = {"allowed": "green", "warning": "amber", "denied": "red"}


def words(kind: str) -> dict[str, str]:
    return KIND_WORDS.get(kind, KIND_WORDS["access"])
