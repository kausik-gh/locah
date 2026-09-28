"""The message template library (Capability Universe §12.4).

"Templates: order confirmed, out for delivery, delivered, booking reminder,
renewal and payment due — pre-approved in English, Tamil and Hindi." Outside
the customer's 24-hour window a template is the only thing WhatsApp lets a
business send (§9.1), so every automatic message LOCAH sends is one of these.

Each template is submitted per business (per WhatsApp Business Account and
language) and used only once approved. Parameters are numbered in the order
they appear in every language, and no body starts or ends on a parameter.
The Tamil and Hindi wording must be read by a native speaker before it is
submitted for a real number (VB-22).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LANGUAGES = {"en": "English", "ta": "Tamil", "hi": "Hindi"}
# Meta's language codes for the library's languages.
META_LANGUAGE = {"en": "en", "ta": "ta", "hi": "hi"}


@dataclass(frozen=True)
class Template:
    key: str
    label: str  # owner words
    category: str  # utility | marketing (Meta's pricing categories)
    audience: str  # customer | staff
    params: tuple[str, ...]  # owner words for each {{n}}, in order
    bodies: dict[str, str]
    sent_when: str  # owner words
    phase: str = "P1"  # P2/P3 templates are in the library; nothing sends them yet


LIBRARY: dict[str, Template] = {t.key: t for t in (
    Template(
        "order_received", "Order received", "utility", "customer",
        ("customer's name", "business name", "order number", "order total"),
        {
            "en": "Hi {{1}}, {{2}} has received your order {{3}} for {{4}}. We will message you when it is confirmed.",
            "ta": "வணக்கம் {{1}}, {{2}} உங்கள் ஆர்டர் {{3}} ({{4}}) பெற்றுக்கொண்டது. உறுதி செய்ததும் உங்களுக்குச் செய்தி அனுப்புவோம்.",
            "hi": "नमस्ते {{1}}, {{2}} को आपका ऑर्डर {{3}} ({{4}}) मिल गया है। पुष्टि होते ही हम आपको संदेश भेजेंगे।",
        },
        "A customer places an order on your website or WhatsApp",
    ),
    Template(
        "order_confirmed", "Order confirmed", "utility", "customer",
        ("order number", "business name", "order total"),
        {
            "en": "Your order {{1}} from {{2}} is confirmed. Total: {{3}}. We will send updates here.",
            "ta": "உங்கள் ஆர்டர் {{1}} ({{2}}) உறுதி செய்யப்பட்டது. மொத்தம்: {{3}}. புதுப்பிப்புகளை இங்கே அனுப்புவோம்.",
            "hi": "आपका ऑर्डर {{1}} ({{2}}) कन्फ़र्म हो गया है। कुल: {{3}}। आगे की जानकारी हम यहीं भेजेंगे।",
        },
        "You accept an order",
    ),
    Template(
        "order_out_for_delivery", "Out for delivery", "utility", "customer",
        ("order number", "business name", "tracking link"),
        {
            "en": "Your order {{1}} from {{2}} is on its way. Track it live: {{3}} (the link works until delivery).",
            "ta": "உங்கள் ஆர்டர் {{1}} ({{2}}) வழியில் உள்ளது. நேரலையில் பார்க்க: {{3}} (டெலிவரி வரை இந்த இணைப்பு செயல்படும்).",
            "hi": "आपका ऑर्डर {{1}} ({{2}}) रास्ते में है। लाइव ट्रैक करें: {{3}} (डिलीवरी तक यह लिंक चलेगा)।",
        },
        "An order is picked up for delivery",
    ),
    Template(
        "order_delivered", "Delivered", "utility", "customer",
        ("order number", "business name"),
        {
            "en": "Your order {{1}} from {{2}} has been delivered. Thank you for shopping with us.",
            "ta": "உங்கள் ஆர்டர் {{1}} ({{2}}) டெலிவரி செய்யப்பட்டது. எங்களிடம் வாங்கியதற்கு நன்றி.",
            "hi": "आपका ऑर्डर {{1}} ({{2}}) डिलीवर हो गया है। हमसे ख़रीदारी के लिए धन्यवाद।",
        },
        "An order is delivered",
    ),
    Template(
        "booking_confirmed", "Booking confirmed", "utility", "customer",
        ("business name", "date and time", "what is booked"),
        {
            "en": "Your booking with {{1}} is confirmed for {{2}} ({{3}}). Reply here if you need to change it.",
            "ta": "உங்கள் முன்பதிவு உறுதி: {{1}}, {{2}} ({{3}}). மாற்ற வேண்டுமெனில் இங்கே பதில் அனுப்புங்கள்.",
            "hi": "आपकी बुकिंग पक्की है: {{1}}, {{2}} ({{3}})। बदलना हो तो यहाँ जवाब दें।",
        },
        "A booking is confirmed",
    ),
    Template(
        "booking_reminder", "Booking reminder", "utility", "customer",
        ("business name", "date and time", "what is booked"),
        {
            "en": "Reminder: your booking with {{1}} is on {{2}} ({{3}}). Reply here if you cannot make it.",
            "ta": "நினைவூட்டல்: {{1}} உடன் உங்கள் முன்பதிவு {{2}} ({{3}}). வர முடியாவிட்டால் இங்கே பதில் அனுப்புங்கள்.",
            "hi": "याद दिलाना: {{1}} के साथ आपकी बुकिंग {{2}} को है ({{3}})। न आ सकें तो यहाँ जवाब दें।",
        },
        "Before a booking, on the booking reminder schedule",
    ),
    Template(
        "payment_due", "Payment due", "utility", "customer",
        ("business name", "amount due", "link to see and pay"),
        {
            "en": "Hello, this is {{1}}. {{2}} is due on your account. See the details and pay here: {{3}} — thank you.",
            "ta": "வணக்கம், இது {{1}}. உங்கள் கணக்கில் {{2}} செலுத்த வேண்டியுள்ளது. விவரம் பார்த்துச் செலுத்த: {{3}} — நன்றி.",
            "hi": "नमस्ते, यह {{1}} है। आपके खाते में {{2}} बाकी है। विवरण देखें और भुगतान करें: {{3}} — धन्यवाद।",
        },
        "A khata balance or a bill is past its due date, on the reminder schedule; or you send a statement",
    ),
    Template(
        "bill_ready", "Your bill", "utility", "customer",
        ("business name", "bill number", "amount", "link to the bill"),
        {
            "en": "Your bill from {{1}}: {{2}} for {{3}}. View or download it here: {{4}} — thank you.",
            "ta": "உங்கள் பில் ({{1}}): {{2}}, தொகை {{3}}. பார்க்க அல்லது பதிவிறக்க: {{4}} — நன்றி.",
            "hi": "आपका बिल ({{1}}): {{2}}, राशि {{3}}। देखें या डाउनलोड करें: {{4}} — धन्यवाद।",
        },
        "You send a bill from its page",
    ),
    Template(
        "renewal_due", "Renewal due", "utility", "customer",
        ("plan name", "business name", "end date", "renewal link"),
        {
            "en": "Your {{1}} plan with {{2}} ends on {{3}}. Renew here: {{4}} — thank you.",
            "ta": "உங்கள் {{1}} திட்டம் ({{2}}) {{3}} அன்று முடிகிறது. புதுப்பிக்க: {{4}} — நன்றி.",
            "hi": "आपका {{1}} प्लान ({{2}}) {{3}} को ख़त्म हो रहा है। रिन्यू करें: {{4}} — धन्यवाद।",
        },
        "Before a membership ends (renewal reminders arrive with memberships, P2)", phase="P2",
    ),
    Template(
        "offer_announcement", "Offer", "marketing", "customer",
        ("business name", "the offer"),
        {
            "en": "News from {{1}}: {{2}}. Reply STOP to stop offers.",
            "ta": "புதிய தகவல் ({{1}}): {{2}}. சலுகைகள் வேண்டாமெனில் STOP என்று பதில் அனுப்புங்கள்.",
            "hi": "नई ख़बर ({{1}}): {{2}}। ऑफ़र बंद करने के लिए STOP लिखें।",
        },
        "Campaigns to customers who opted in (campaigns arrive in P3)", phase="P3",
    ),
    Template(
        "staff_alert", "Alert to your team", "utility", "staff",
        ("business name", "what happened"),
        {
            "en": "LOCAH alert for {{1}}: {{2}}. Open LOCAH to act on it.",
            "ta": "LOCAH அறிவிப்பு ({{1}}): {{2}}. நடவடிக்கை எடுக்க LOCAH-ஐத் திறக்கவும்.",
            "hi": "LOCAH सूचना ({{1}}): {{2}}। कार्रवाई के लिए LOCAH खोलें।",
        },
        "Something a team member asked to be told about on WhatsApp happens",
    ),
)}

_PARAM = re.compile(r"\{\{(\d+)\}\}")


def check_library() -> list[str]:
    """Problems that would get a template rejected — run by the tests."""
    problems = []
    for t in LIBRARY.values():
        for lang in LANGUAGES:
            body = t.bodies.get(lang)
            if body is None:
                problems.append(f"{t.key}: no {lang}")
                continue
            found = [int(n) for n in _PARAM.findall(body)]
            if found != list(range(1, len(t.params) + 1)):
                problems.append(f"{t.key}/{lang}: parameters {found} should be 1..{len(t.params)} in order")
            if body.startswith("{{") or body.rstrip(" .।").endswith("}}"):
                problems.append(f"{t.key}/{lang}: starts or ends on a parameter")
            if len(body) > 1024:
                problems.append(f"{t.key}/{lang}: longer than 1024 characters")
    return problems


def render(key: str, language: str, params: list[str]) -> str:
    """The text the customer sees, for the transcript and previews."""
    t = LIBRARY[key]
    body = t.bodies.get(language) or t.bodies["en"]
    return _PARAM.sub(lambda m: params[int(m.group(1)) - 1] if int(m.group(1)) <= len(params) else m.group(0), body)


def library_view() -> list[dict[str, object]]:
    return [{"key": t.key, "label": t.label, "category": t.category, "audience": t.audience, "params": list(t.params),
             "bodies": t.bodies, "sent_when": t.sent_when, "phase": t.phase} for t in LIBRARY.values()]
