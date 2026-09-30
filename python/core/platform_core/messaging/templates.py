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
    category: str  # utility | marketing | authentication (Meta's pricing categories)
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
        # Meta allows one-time codes only in its preset authentication format
        # (checked 2026-09-30): Meta writes the words; LOCAH supplies the code,
        # shown in the body and behind a copy-code button. These bodies are
        # what the customer sees, kept for the inbox transcript.
        "quote_acceptance_code", "Code to accept a quote", "authentication", "customer",
        ("the 6-digit code",),
        {
            "en": "{{1}} is your verification code. For your security, do not share this code. "
                  "This code expires in 10 minutes.",
            "ta": "{{1}} உங்கள் சரிபார்ப்புக் குறியீடு. உங்கள் பாதுகாப்பிற்காக, இதை யாருடனும் பகிர வேண்டாம். "
                  "இந்தக் குறியீடு 10 நிமிடங்களில் காலாவதியாகும்.",
            "hi": "{{1}} आपका सत्यापन कोड है। अपनी सुरक्षा के लिए यह कोड किसी से साझा न करें। "
                  "यह कोड 10 मिनट में समाप्त हो जाएगा।",
        },
        "A customer asks for the code to accept a quote on its page", phase="P2",
    ),
    Template(
        "queue_turn_soon", "Your turn soon", "utility", "customer",
        ("business name", "token number", "how many are ahead"),
        {
            "en": "Your turn at {{1}} is coming up: token {{2}}, {{3}} ahead of you. Please be ready.",
            "ta": "நினைவூட்டல்: {{1}} இல் உங்கள் முறை நெருங்குகிறது — டோக்கன் {{2}}, உங்களுக்கு முன் {{3}} பேர். தயாராக இருங்கள்.",
            "hi": "सूचना: {{1}} पर आपकी बारी आने वाली है — टोकन {{2}}, आपसे पहले {{3}}। कृपया तैयार रहें।",
        },
        "When a queue token is next in line (the lane's 'tell them when … ahead')", phase="P2",
    ),
    Template(
        "booking_waitlist_opening", "A place opened up", "utility", "customer",
        ("business name", "what is booked", "date and time", "link to take it", "minutes it is held"),
        {
            "en": "Good news from {{1}}: a place opened up for {{2}} on {{3}}. Take it here: {{4}} (kept for you for {{5}} minutes, then offered to the next person).",
            "ta": "நல்ல செய்தி: {{1}} இல் {{2}} க்கு {{3}} அன்று இடம் கிடைத்துள்ளது. இங்கே பெறுங்கள்: {{4}} ({{5}} நிமிடங்கள் உங்களுக்காக வைத்திருப்போம், பின்னர் அடுத்தவருக்கு).",
            "hi": "खुशखबरी: {{1}} में {{2}} के लिए {{3}} को जगह खाली हुई है। यहाँ लें: {{4}} ({{5}} मिनट तक आपके लिए रखी है, फिर अगले व्यक्ति को)।",
        },
        "A place a customer is waiting for opens up (Bookings waitlist)", phase="P2",
    ),
    Template(
        "booking_missed", "We missed you", "utility", "customer",
        ("business name", "what was booked", "date and time", "link to book again"),
        {
            "en": "Hello from {{1}}: we missed you for {{2}} on {{3}}. Book another time here: {{4}} (or reply to this message).",
            "ta": "வணக்கம்: {{1}} இல் {{2}} ({{3}}) க்கு உங்களைக் காணவில்லை. வேறு நேரம் முன்பதிவு செய்ய: {{4}} (அல்லது இங்கே பதில் அனுப்புங்கள்).",
            "hi": "नमस्ते: {{1}} में {{2}} ({{3}}) के लिए आप नहीं आ पाए। दूसरा समय यहाँ बुक करें: {{4}} (या इस संदेश का जवाब दें)।",
        },
        "A booking is marked no-show (Bookings no-show follow-up)", phase="P2",
    ),
    Template(
        "review_request", "Review request", "utility", "customer",
        ("business name", "completed order or booking", "review link"),
        {
            "en": "Thanks for choosing {{1}}. Tell us about {{2}} here: {{3}}. Your feedback helps us improve.",
            "ta": "வணக்கம்! {{1}}-ஐ தேர்ந்தெடுத்ததற்கு நன்றி. {{2}} பற்றி உங்கள் கருத்தை இங்கே பகிருங்கள்: {{3}}. இது எங்களுக்கு உதவும்.",
            "hi": "नमस्ते! {{1}} को चुनने के लिए धन्यवाद। {{2}} के बारे में यहाँ अपनी राय दें: {{3}}। आपकी राय हमें बेहतर बनाती है।",
        },
        "After a completed order or booking, if the customer has not reviewed or declined",
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
        "Before a membership, subscription or contract ends (Automations › Renewal reminders)", phase="P2",
    ),
    Template(
        "membership_grace", "Membership in grace", "utility", "customer",
        ("plan name", "business name", "end date", "last day of grace", "renewal link"),
        {
            "en": "Your {{1}} plan with {{2}} ended on {{3}}. You can still renew until {{4}}: {{5}} — thank you.",
            "ta": "உங்கள் {{1}} திட்டம் ({{2}}) {{3}} அன்று முடிந்தது. {{4}} வரை புதுப்பிக்கலாம்: {{5}} — நன்றி.",
            "hi": "आपका {{1}} प्लान ({{2}}) {{3}} को ख़त्म हो गया। आप {{4}} तक रिन्यू कर सकते हैं: {{5}} — धन्यवाद।",
        },
        "The day after a plan ends without renewal, when the plan has a grace period", phase="P2",
    ),
    Template(
        "membership_expired", "Membership expired", "utility", "customer",
        ("plan name", "business name", "renewal link"),
        {
            "en": "Your {{1}} plan with {{2}} has expired. Renew any time here: {{3}} — thank you.",
            "ta": "உங்கள் {{1}} திட்டம் ({{2}}) காலாவதியாகிவிட்டது. எப்போது வேண்டுமானாலும் புதுப்பிக்க: {{3}} — நன்றி.",
            "hi": "आपका {{1}} प्लान ({{2}}) समाप्त हो गया है। कभी भी यहाँ रिन्यू करें: {{3}} — धन्यवाद।",
        },
        "A plan expires without renewal", phase="P2",
    ),
    Template(
        "membership_renewed", "Payment received for a plan", "utility", "customer",
        ("business name", "plan name", "valid until"),
        {
            "en": "Thank you — {{1}} has received your payment. Your {{2}} plan is valid until {{3}}. See you soon.",
            "ta": "நன்றி — {{1}} உங்கள் கட்டணத்தைப் பெற்றது. உங்கள் {{2}} திட்டம் {{3}} வரை செல்லும்.",
            "hi": "धन्यवाद — {{1}} को आपका भुगतान मिल गया है। आपका {{2}} प्लान {{3}} तक मान्य है।",
        },
        "A membership, subscription or contract period is paid", phase="P2",
    ),
    Template(
        "membership_winback", "We miss you (win-back)", "marketing", "customer",
        ("business name", "plan name", "link"),
        {
            "en": "We miss you at {{1}}. Come back to your {{2}} plan any time: {{3}}. Reply STOP to stop offers.",
            "ta": "உங்களை {{1}} நினைக்கிறது. உங்கள் {{2}} திட்டத்திற்கு எப்போது வேண்டுமானாலும் திரும்பலாம்: {{3}}. சலுகைகள் வேண்டாமெனில் STOP என்று பதில் அனுப்புங்கள்.",
            "hi": "आपकी याद {{1}} को आती है। अपने {{2}} प्लान पर कभी भी लौटें: {{3}}। ऑफ़र बंद करने के लिए STOP लिखें।",
        },
        "15 days after a plan expired — only to customers who opted in to offers", phase="P2",
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
# Minutes an authentication code stays valid (Meta's code_expiration_minutes).
CODE_EXPIRY_MINUTES = 10


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
            # Meta's own preset authentication wording starts on the code; the
            # rule is for LOCAH-written bodies.
            if t.category != "authentication" and (body.startswith("{{") or body.rstrip(" .।").endswith("}}")):
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
