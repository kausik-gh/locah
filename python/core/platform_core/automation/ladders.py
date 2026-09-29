"""The ladders LOCAH runs — each a timed sequence of steps tied to one entity.

Defaults come from the sources (Capability Universe §10.4 renewal ladder;
Business OS Guide §6 automation pattern); owners edit offsets and switch steps
or whole ladders off (automation_rules). A ladder is only offered to an owner
when its module is built and switched on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class LadderStep:
    key: str
    offset: timedelta  # from the ladder's anchor (e.g. the plan's end date)
    when: str  # owner words: "7 days before the plan ends"
    does: str  # owner words: "WhatsApp reminder with a pay button"
    marketing: bool = False  # needs marketing consent, sent as a marketing template


@dataclass(frozen=True)
class Ladder:
    key: str
    module: str
    label: str
    anchor: str  # owner words for what the offsets count from
    entity_type: str
    steps: tuple[LadderStep, ...]
    stops_when: str  # owner words (Guide §6 "Stops/changes when")
    quiet_hours: bool = True


D = timedelta(days=1)
H = timedelta(hours=1)

LADDERS: dict[str, Ladder] = {lad.key: lad for lad in (
    Ladder(
        "membership.renewal", "memberships", "Renewal reminders", "the plan's end date", "member_subscription",
        (
            LadderStep("t_minus_7", -7 * D, "7 days before the plan ends", "Reminder with a Renew button; payment link created"),
            LadderStep("t_minus_2", -2 * D, "2 days before", "Reminder with the amount and plan name (same link)"),
            LadderStep("t0", timedelta(0), "On the end date", "“Your plan ends today”; autopay attempted where set up"),
            LadderStep("t_plus_1", 1 * D, "1 day after", "Grace-period notice; status moves to grace"),
            LadderStep("grace_end", 0 * D, "When grace ends", "“Your membership has expired”; status moves to expired"),
            LadderStep("t_plus_15", 15 * D, "15 days after", "Win-back offer", marketing=True),
        ),
        "the member renews, pauses, or you switch it off",
    ),
    Ladder(
        "membership.instalment", "memberships", "Fee reminders", "each instalment's due date",
        "membership_instalment",
        (
            LadderStep("minus_3", -3 * D, "3 days before", "Reminder to whoever pays, with a payment link"),
            LadderStep("due_day", timedelta(0), "On the due date", "“Due today” with the same link"),
            LadderStep("plus_3", 3 * D, "3 days late", "Late reminder; it shows in Needs you now"),
        ),
        "the instalment is paid or waived, or the enrolment ends",
    ),
    Ladder(
        "booking.reminder", "bookings", "Booking reminders", "the booking's start time", "booking",
        (
            LadderStep("day_before", -1 * D, "The day before", "Confirmation and reminder"),
            LadderStep("two_hours", -2 * H, "2 hours before", "Reminder with time and directions"),
        ),
        "the booking is cancelled or rescheduled",
    ),
    Ladder(
        "invoice.overdue", "invoicing", "Payment reminders", "the invoice due date", "invoice",
        (
            LadderStep("due_day", timedelta(0), "On the due date", "Statement with a payment link"),
            LadderStep("plus_7", 7 * D, "7 days late", "Second reminder"),
            LadderStep("plus_15", 15 * D, "15 days late", "Final reminder; you are told in Needs you now"),
        ),
        "the invoice is paid or you pause it",
    ),
    Ladder(
        "ledger.statement", "ledger", "Khata reminders", "the date the balance became due", "ledger_account",
        (
            LadderStep("due_day", timedelta(0), "When a balance is due", "WhatsApp statement with a payment link"),
            LadderStep("plus_7", 7 * D, "7 days later", "Second reminder"),
        ),
        "the balance is settled or you pause it",
    ),
    Ladder(
        "stock.low", "inventory", "Low-stock alerts", "the moment stock falls below its reorder point", "inventory_record",
        (LadderStep("now", timedelta(0), "Straight away", "Alert everyone who looks after stock, in Notifications"),),
        "stock is restored or the threshold changes",
        quiet_hours=False,
    ),
    Ladder(
        "order.tracking", "fulfilment", "Order updates", "each change in the order's delivery", "order",
        (LadderStep("picked_up", timedelta(0), "When the order is picked up", "Tracking link to the customer"),),
        "the order is delivered or fails",
    ),
    Ladder(
        "review.request", "reviews", "Review requests", "when an order or booking is completed", "interaction",
        (LadderStep("after", 2 * H, "2 hours after completion", "Ask for a review (one per completed interaction)"),),
        "the customer has reviewed or opted out",
    ),
    Ladder(
        "lead.followup", "leads", "Lead follow-ups", "the follow-up date you set", "lead",
        (LadderStep("due", timedelta(0), "On the follow-up date", "Nudge whoever the lead is assigned to (or your sales team)"),),
        "the lead moves stage or closes",
        quiet_hours=False,
    ),
    Ladder(
        "chat.waiting", "messaging", "Chats waiting for a person", "when a customer asks for a person on WhatsApp",
        "messaging_conversation",
        (LadderStep("after_10_min", 10 * timedelta(minutes=1), "After 10 minutes without a reply",
                    "Alert whoever handles WhatsApp; the chat shows in Needs you now"),),
        "someone replies or the chat is closed",
        quiet_hours=False,
    ),
    Ladder(
        "compliance.due", "compliance", "Licences & filing reminders", "the date you entered", "compliance_item",
        (
            LadderStep("minus_30", -30 * D, "30 days before", "Notify whoever handles licences and filings"),
            LadderStep("minus_7", -7 * D, "7 days before", "Reminder in Notifications and Needs you now"),
            LadderStep("minus_1", -1 * D, "The day before", "Final reminder"),
            LadderStep("due", timedelta(0), "On the date entered", "Due today alert"),
        ),
        "the item is renewed, filed, archived or its date is changed",
        quiet_hours=False,
    ),
    Ladder(
        "inventory.expiry", "inventory", "Expiry alerts", "the batch's expiry date", "inventory_batch",
        (
            LadderStep("minus_30", -30 * D, "30 days before", "Tell whoever looks after stock at that location"),
            LadderStep("minus_7", -7 * D, "7 days before", "Reminder in Notifications and Needs you now"),
            LadderStep("expiry", timedelta(0), "On the expiry date", "Expired today — write it off or return it"),
        ),
        "the batch is sold out or written off",
        quiet_hours=False,
    ),
)}
