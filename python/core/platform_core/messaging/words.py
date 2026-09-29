"""The words LOCAH's WhatsApp journeys say, in English, Tamil and Hindi (MD §2
rule 10 "English + Tamil + Hindi (code-mixed input accepted)"; §26.3 P1-10
"English / Tamil / Hindi strings").

Each phrase is keyed by its English wording, so the journeys stay readable in
English and a test checks that every phrase they use has a Tamil and a Hindi
wording. Values in {braces} are filled in after choosing the language; owner
data (item names, the business name, choice labels) is never translated.

The customer's language is the one they chose ("Language · மொழி · भाषा" in the
menu), else the one their own messages are written in (Tamil or Devanagari
script), else the business's WhatsApp language. Latin-script Tamil or Hindi
("Tanglish", "Hinglish") cannot be told apart from English reliably, so it
does not switch the language.

The Tamil and Hindi wording here must be read by a native speaker before a
pilot goes live (as for the templates, VB-22).
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

LANGS = ("en", "ta", "hi")
LANGUAGE_NAMES = {"en": "English", "ta": "தமிழ்", "hi": "हिंदी"}

# English wording → {"ta": ..., "hi": ...}
PHRASES: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------------- menu
    "Hi {name}! This is {business}. What would you like to do?": {
        "ta": "வணக்கம் {name}! இது {business}. என்ன செய்ய விரும்புகிறீர்கள்?",
        "hi": "नमस्ते {name}! यह {business} है। आप क्या करना चाहेंगे?"},
    "Hi there! This is {business}. What would you like to do?": {
        "ta": "வணக்கம்! இது {business}. என்ன செய்ய விரும்புகிறீர்கள்?",
        "hi": "नमस्ते! यह {business} है। आप क्या करना चाहेंगे?"},
    "Menu": {"ta": "மெனு", "hi": "मेनू"},
    "Choose": {"ta": "தேர்வு செய்யுங்கள்", "hi": "चुनें"},
    "Order": {"ta": "ஆர்டர் செய்ய", "hi": "ऑर्डर करें"},
    "See what we have and order here": {"ta": "எங்களிடம் உள்ளதைப் பார்த்து இங்கே ஆர்டர் செய்யுங்கள்",
                                        "hi": "हमारे पास क्या है देखें और यहीं ऑर्डर करें"},
    "Book": {"ta": "முன்பதிவு", "hi": "बुक करें"},
    "Pick a service and a time": {"ta": "சேவையையும் நேரத்தையும் தேர்வு செய்யுங்கள்", "hi": "सेवा और समय चुनें"},
    "Ask a question": {"ta": "கேள்வி கேட்க", "hi": "सवाल पूछें"},
    "About a product, service or price": {"ta": "பொருள், சேவை அல்லது விலை பற்றி",
                                          "hi": "किसी सामान, सेवा या दाम के बारे में"},
    "Track my order": {"ta": "என் ஆர்டர் எங்கே", "hi": "मेरा ऑर्डर कहाँ है"},
    "Where your order is now": {"ta": "உங்கள் ஆர்டர் இப்போது எங்கே உள்ளது", "hi": "आपका ऑर्डर अभी कहाँ है"},
    "Repeat my last order": {"ta": "கடைசி ஆர்டரை மீண்டும்", "hi": "पिछला ऑर्डर दोबारा"},
    "Same items, today's prices": {"ta": "அதே பொருட்கள், இன்றைய விலையில்", "hi": "वही सामान, आज के दाम पर"},
    "What do I owe": {"ta": "என் பாக்கி எவ்வளவு", "hi": "मेरा कितना बाकी है"},
    "Your balance and bills": {"ta": "உங்கள் பாக்கியும் பில்களும்", "hi": "आपका बकाया और बिल"},
    "Change or cancel": {"ta": "மாற்ற / ரத்து செய்ய", "hi": "बदलें या रद्द करें"},
    "An order or a booking": {"ta": "ஆர்டர் அல்லது முன்பதிவு", "hi": "ऑर्डर या बुकिंग"},
    "Talk to a person": {"ta": "ஒருவரிடம் பேச", "hi": "किसी से बात करें"},
    "Someone from the team replies here": {"ta": "எங்கள் குழுவினர் இங்கே பதிலளிப்பார்கள்",
                                           "hi": "हमारी टीम से कोई यहीं जवाब देगा"},
    "Done — we'll write to you in English.": {"ta": "சரி — இனி உங்களுக்குத் தமிழில் எழுதுவோம்.",
                                              "hi": "ठीक है — अब हम आपको हिंदी में लिखेंगे।"},
    # ---------------------------------------------------------------- order
    "Ordering on WhatsApp is not available right now. Tap Talk to a person, or send menu.": {
        "ta": "இப்போது WhatsApp-இல் ஆர்டர் செய்ய முடியாது. 'ஒருவரிடம் பேச' என்பதைத் தட்டுங்கள், அல்லது மெனு என்று அனுப்புங்கள்.",
        "hi": "अभी WhatsApp पर ऑर्डर नहीं हो सकता। 'किसी से बात करें' दबाएँ, या मेनू भेजें।"},
    "Other": {"ta": "மற்றவை", "hi": "अन्य"},
    "1 item": {"ta": "1 பொருள்", "hi": "1 आइटम"},
    "{n} items": {"ta": "{n} பொருட்கள்", "hi": "{n} आइटम"},
    "Other items": {"ta": "மற்ற பொருட்கள்", "hi": "अन्य आइटम"},
    "What would you like to order?": {"ta": "என்ன ஆர்டர் செய்ய விரும்புகிறீர்கள்?", "hi": "आप क्या ऑर्डर करना चाहेंगे?"},
    "Categories": {"ta": "வகைகள்", "hi": "श्रेणियाँ"},
    "More items…": {"ta": "மேலும் பொருட்கள்…", "hi": "और आइटम…"},
    "{n} more": {"ta": "இன்னும் {n}", "hi": "{n} और"},
    "Choose an item — prices are today's.": {"ta": "ஒரு பொருளைத் தேர்வு செய்யுங்கள் — விலைகள் இன்றையவை.",
                                             "hi": "एक आइटम चुनें — दाम आज के हैं।"},
    "Items": {"ta": "பொருட்கள்", "hi": "आइटम"},
    "Checkout (1 item)": {"ta": "முடிக்க (1 பொருள்)", "hi": "चेकआउट (1 आइटम)"},
    "Checkout ({n} items)": {"ta": "முடிக்க ({n} பொருட்கள்)", "hi": "चेकआउट ({n} आइटम)"},
    "{amount} so far": {"ta": "இதுவரை {amount}", "hi": "अब तक {amount}"},
    "Choose an option": {"ta": "ஒன்றைத் தேர்வு செய்யுங்கள்", "hi": "विकल्प चुनें"},
    "That item is no longer available.": {"ta": "அந்தப் பொருள் இப்போது கிடைக்கவில்லை.",
                                          "hi": "वह आइटम अब उपलब्ध नहीं है।"},
    "{item}: which one?": {"ta": "{item}: எது வேண்டும்?", "hi": "{item}: कौन सा?"},
    "Options": {"ta": "தேர்வுகள்", "hi": "विकल्प"},
    "{item}: how much?": {"ta": "{item}: எவ்வளவு?", "hi": "{item}: कितना?"},
    "Sizes": {"ta": "அளவுகள்", "hi": "साइज़"},
    "{item}: type the {group} (up to {n} letters).": {
        "ta": "{item}: {group} தட்டச்சு செய்யுங்கள் ({n} எழுத்துகள் வரை).",
        "hi": "{item}: {group} लिखें ({n} अक्षरों तक)।"},
    "No {group}": {"ta": "{group} வேண்டாம்", "hi": "{group} नहीं"},
    "{item}: {group}?": {"ta": "{item}: {group}?", "hi": "{item}: {group}?"},
    "How many {item}?": {"ta": "{item} எத்தனை?", "hi": "{item} कितने?"},
    "Or type a number.": {"ta": "அல்லது எண்ணைத் தட்டச்சு செய்யுங்கள்.", "hi": "या कोई संख्या लिखें।"},
    "That is {count} letters — up to {max}, please. Type it again.": {
        "ta": "இது {count} எழுத்துகள் — {max} வரை மட்டும். மீண்டும் தட்டச்சு செய்யுங்கள்.",
        "hi": "यह {count} अक्षर हैं — {max} तक ही। दोबारा लिखें।"},
    "Type how many as a number, like 2.": {"ta": "எத்தனை என்று எண்ணாக எழுதுங்கள், உதாரணம் 2.",
                                           "hi": "कितने चाहिए, संख्या में लिखें, जैसे 2।"},
    "Added. Your cart: 1 item, {amount}.": {"ta": "சேர்க்கப்பட்டது. உங்கள் கூடை: 1 பொருள், {amount}.",
                                            "hi": "जोड़ दिया। आपकी टोकरी: 1 आइटम, {amount}।"},
    "Added. Your cart: {n} items, {amount}.": {"ta": "சேர்க்கப்பட்டது. உங்கள் கூடை: {n} பொருட்கள், {amount}.",
                                               "hi": "जोड़ दिया। आपकी टोकरी: {n} आइटम, {amount}।"},
    "Add more": {"ta": "மேலும் சேர்க்க", "hi": "और जोड़ें"},
    "Checkout": {"ta": "ஆர்டர் முடிக்க", "hi": "चेकआउट"},
    "{name} is no longer available.": {"ta": "{name} இப்போது கிடைக்கவில்லை.", "hi": "{name} अब उपलब्ध नहीं है।"},
    "{name} needs choosing again.": {"ta": "{name} — மீண்டும் தேர்வு செய்ய வேண்டும்.", "hi": "{name} फिर से चुनना होगा।"},
    "{name} has only {n} left.": {"ta": "{name} {n} மட்டுமே உள்ளது.", "hi": "{name} सिर्फ़ {n} बचे हैं।"},
    "{name} is out of stock.": {"ta": "{name} இருப்பில் இல்லை.", "hi": "{name} स्टॉक में नहीं है।"},
    "An item": {"ta": "ஒரு பொருள்", "hi": "एक आइटम"},
    "Your cart is empty.": {"ta": "உங்கள் கூடை காலியாக உள்ளது.", "hi": "आपकी टोकरी खाली है।"},
    "We can't take orders here right now.": {"ta": "இப்போது இங்கே ஆர்டர் எடுக்க முடியாது.",
                                             "hi": "अभी हम यहाँ ऑर्डर नहीं ले सकते।"},
    "Delivery or pickup?": {"ta": "டெலிவரியா, நேரில் வாங்குவதா?", "hi": "डिलीवरी या पिकअप?"},
    "Delivery": {"ta": "டெலிவரி", "hi": "डिलीवरी"},
    "Pickup": {"ta": "நேரில் வாங்க", "hi": "पिकअप"},
    "As soon as possible": {"ta": "முடிந்தவரை விரைவில்", "hi": "जल्द से जल्द"},
    "No day is open for these items right now.": {"ta": "இந்தப் பொருட்களுக்கு இப்போது எந்த நாளும் இல்லை.",
                                                  "hi": "इन आइटम के लिए अभी कोई दिन खाली नहीं है।"},
    "Change the cart": {"ta": "கூடையை மாற்ற", "hi": "टोकरी बदलें"},
    "When do you need it?": {"ta": "எப்போது வேண்டும்?", "hi": "आपको कब चाहिए?"},
    "Earliest: {when}.": {"ta": "முதல் வாய்ப்பு: {when}.", "hi": "सबसे जल्दी: {when}।"},
    "Days": {"ta": "நாட்கள்", "hi": "दिन"},
    "That day is not open any more.": {"ta": "அந்த நாள் இப்போது கிடைக்கவில்லை.", "hi": "वह दिन अब खाली नहीं है।"},
    "{day}: what time?": {"ta": "{day}: எந்த நேரம்?", "hi": "{day}: किस समय?"},
    "Times": {"ta": "நேரங்கள்", "hi": "समय"},
    "Delivery — {amount}": {"ta": "டெலிவரி — {amount}", "hi": "डिलीवरी — {amount}"},
    "Total {amount}": {"ta": "மொத்தம் {amount}", "hi": "कुल {amount}"},
    "Remove it": {"ta": "நீக்கு", "hi": "हटाएँ"},
    "Make it {n}": {"ta": "{n} ஆக்கு", "hi": "{n} कर दें"},
    "Deliver to {address}?": {"ta": "{address} — இங்கே டெலிவரி செய்யலாமா?", "hi": "{address} पर डिलीवरी करें?"},
    "Yes, same address": {"ta": "ஆம், அதே முகவரி", "hi": "हाँ, वही पता"},
    "New address": {"ta": "புதிய முகவரி", "hi": "नया पता"},
    "Location pin": {"ta": "இருப்பிடக் குறி", "hi": "लोकेशन पिन"},
    "your address": {"ta": "உங்கள் முகவரி", "hi": "आपका पता"},
    "Send your location pin (tap + → Location), or type your address with its PIN code.": {
        "ta": "உங்கள் இருப்பிடத்தை அனுப்புங்கள் (+ → Location), அல்லது முகவரியை PIN குறியீட்டுடன் தட்டச்சு செய்யுங்கள்.",
        "hi": "अपनी लोकेशन भेजें (+ → Location), या पिन कोड के साथ अपना पता लिखें।"},
    "Type the full address with its PIN code, or send your location pin.": {
        "ta": "முழு முகவரியை PIN குறியீட்டுடன் தட்டச்சு செய்யுங்கள், அல்லது இருப்பிடத்தை அனுப்புங்கள்.",
        "hi": "पूरा पता पिन कोड के साथ लिखें, या अपनी लोकेशन भेजें।"},
    "Sorry — we don't deliver there yet.": {"ta": "மன்னிக்கவும் — அங்கே இன்னும் டெலிவரி செய்வதில்லை.",
                                            "hi": "माफ़ कीजिए — हम अभी वहाँ डिलीवरी नहीं करते।"},
    "Pickup instead": {"ta": "நேரில் வாங்குகிறேன்", "hi": "पिकअप करें"},
    "Another address": {"ta": "வேறு முகவரி", "hi": "दूसरा पता"},
    "Paying online on WhatsApp is not available yet. A person will help you finish this order.": {
        "ta": "WhatsApp-இல் ஆன்லைனில் பணம் செலுத்துவது இன்னும் இல்லை. இந்த ஆர்டரை முடிக்க ஒருவர் உதவுவார்.",
        "hi": "WhatsApp पर ऑनलाइन भुगतान अभी उपलब्ध नहीं है। यह ऑर्डर पूरा करने में कोई आपकी मदद करेगा।"},
    "For a first order, cash on delivery is up to {amount}. A person will help you pay for this one.": {
        "ta": "முதல் ஆர்டருக்கு, டெலிவரியில் பணம் செலுத்துவது {amount} வரை மட்டும். இதற்குப் பணம் செலுத்த ஒருவர் உதவுவார்.",
        "hi": "पहले ऑर्डर पर डिलीवरी के समय नकद भुगतान {amount} तक ही है। इसका भुगतान करने में कोई आपकी मदद करेगा।"},
    "Deliver to {address}": {"ta": "டெலிவரி: {address}", "hi": "डिलीवरी: {address}"},
    "Pay on delivery": {"ta": "டெலிவரியில் பணம்", "hi": "डिलीवरी पर भुगतान"},
    "Pay at pickup": {"ta": "வாங்கும்போது பணம்", "hi": "पिकअप पर भुगतान"},
    "Ready: {when}": {"ta": "தயாராகும்: {when}", "hi": "तैयार: {when}"},
    "Advance {amount} now (a link to pay it follows), the rest on delivery.": {
        "ta": "இப்போது முன்பணம் {amount} (செலுத்த இணைப்பு அனுப்புவோம்), மீதி டெலிவரியில்.",
        "hi": "अभी {amount} एडवांस (भुगतान का लिंक भेजेंगे), बाकी डिलीवरी पर।"},
    "Advance {amount} now (a link to pay it follows), the rest at pickup.": {
        "ta": "இப்போது முன்பணம் {amount} (செலுத்த இணைப்பு அனுப்புவோம்), மீதி வாங்கும்போது.",
        "hi": "अभी {amount} एडवांस (भुगतान का लिंक भेजेंगे), बाकी पिकअप पर।"},
    "Place this order?": {"ta": "இந்த ஆர்டரை உறுதி செய்யலாமா?", "hi": "यह ऑर्डर दें?"},
    "Place order": {"ta": "ஆர்டர் செய்", "hi": "ऑर्डर दें"},
    "Change": {"ta": "மாற்று", "hi": "बदलें"},
    "Cancel": {"ta": "ரத்து", "hi": "रद्द करें"},
    "Your order {number} is already placed.": {"ta": "உங்கள் ஆர்டர் {number} ஏற்கெனவே செய்யப்பட்டது.",
                                               "hi": "आपका ऑर्डर {number} पहले ही दिया जा चुका है।"},
    "A price changed since your summary.": {"ta": "சுருக்கத்துக்குப் பிறகு ஒரு விலை மாறியுள்ளது.",
                                            "hi": "सारांश के बाद एक दाम बदल गया है।"},
    "Place it at this total?": {"ta": "இந்த மொத்தத்தில் ஆர்டர் செய்யலாமா?", "hi": "इस कुल पर ऑर्डर दें?"},
    "That did not go through: {reason}.": {"ta": "அது நடக்கவில்லை: {reason}.", "hi": "यह नहीं हो पाया: {reason}।"},
    "Try again": {"ta": "மீண்டும் முயல", "hi": "फिर कोशिश करें"},
    "Order {number} placed for {amount}. {business} will confirm it here. Follow it: {link}": {
        "ta": "ஆர்டர் {number} {amount}-க்குச் செய்யப்பட்டது. {business} இங்கே உறுதி செய்வார்கள். நிலையைப் பார்க்க: {link}",
        "hi": "ऑर्डर {number} {amount} का दे दिया गया। {business} यहीं पुष्टि करेगा। ऑर्डर देखें: {link}"},
    "Please pay the {amount} advance here: {link}": {"ta": "{amount} முன்பணத்தை இங்கே செலுத்துங்கள்: {link}",
                                                      "hi": "कृपया {amount} एडवांस यहाँ भरें: {link}"},
    "Cart cleared. Send menu any time.": {
        "ta": "கூடை காலி செய்யப்பட்டது. எப்போது வேண்டுமானாலும் மெனு என்று அனுப்புங்கள்.",
        "hi": "टोकरी खाली कर दी। कभी भी मेनू भेजें।"},
    # ---------------------------------------------------------------- book
    "Booking on WhatsApp is not available right now. Tap Talk to a person, or send menu.": {
        "ta": "இப்போது WhatsApp-இல் முன்பதிவு செய்ய முடியாது. 'ஒருவரிடம் பேச' என்பதைத் தட்டுங்கள், அல்லது மெனு என்று அனுப்புங்கள்.",
        "hi": "अभी WhatsApp पर बुकिंग नहीं हो सकती। 'किसी से बात करें' दबाएँ, या मेनू भेजें।"},
    "What would you like to book?": {"ta": "எதை முன்பதிவு செய்ய விரும்புகிறீர்கள்?", "hi": "आप क्या बुक करना चाहेंगे?"},
    "Services": {"ta": "சேவைகள்", "hi": "सेवाएँ"},
    "{n} min": {"ta": "{n} நிமி", "hi": "{n} मिनट"},
    "Where?": {"ta": "எங்கே?", "hi": "कहाँ?"},
    "Locations": {"ta": "இடங்கள்", "hi": "जगहें"},
    "Today": {"ta": "இன்று", "hi": "आज"},
    "Tomorrow": {"ta": "நாளை", "hi": "कल"},
    "Which day?": {"ta": "எந்த நாள்?", "hi": "कौन सा दिन?"},
    "What time on {day}? Type it like 5:30 pm.": {
        "ta": "{day} எந்த நேரம்? 5:30 pm என்பது போல் தட்டச்சு செய்யுங்கள்.",
        "hi": "{day} किस समय? 5:30 pm की तरह लिखें।"},
    "No free times on {day}.": {"ta": "{day} காலியான நேரம் இல்லை.", "hi": "{day} कोई समय खाली नहीं है।"},
    "Another day": {"ta": "வேறு நாள்", "hi": "दूसरा दिन"},
    "Free times on {day}:": {"ta": "{day} காலியான நேரங்கள்:", "hi": "{day} खाली समय:"},
    "Type the time like 5:30 pm.": {"ta": "நேரத்தை 5:30 pm என்பது போல் தட்டச்சு செய்யுங்கள்.",
                                    "hi": "समय 5:30 pm की तरह लिखें।"},
    "That time is not free.": {"ta": "அந்த நேரம் காலியாக இல்லை.", "hi": "वह समय खाली नहीं है।"},
    "Other times": {"ta": "வேறு நேரங்கள்", "hi": "दूसरे समय"},
    "{service} on {day} at {time}. Confirm?": {"ta": "{service} — {day}, {time}. உறுதி செய்யலாமா?",
                                               "hi": "{service} — {day}, {time}। पक्का करें?"},
    "Confirm": {"ta": "உறுதி செய்", "hi": "पक्का करें"},
    "Other time": {"ta": "வேறு நேரம்", "hi": "दूसरा समय"},
    "Booking {number}: {service} on {day} at {time}. It's confirmed.": {
        "ta": "முன்பதிவு {number}: {service} — {day}, {time}. உறுதி செய்யப்பட்டது.",
        "hi": "बुकिंग {number}: {service} — {day}, {time}। पक्की हो गई।"},
    "Booking {number}: {service} on {day} at {time}. {business} will confirm it here.": {
        "ta": "முன்பதிவு {number}: {service} — {day}, {time}. {business} இங்கே உறுதி செய்வார்கள்.",
        "hi": "बुकिंग {number}: {service} — {day}, {time}। {business} यहीं पुष्टि करेगा।"},
    # ---------------------------------------------------------------- enquire
    "What would you like to know? Type your question and we'll get back to you here.": {
        "ta": "என்ன தெரிந்துகொள்ள விரும்புகிறீர்கள்? உங்கள் கேள்வியைத் தட்டச்சு செய்யுங்கள், இங்கே பதில் அனுப்புவோம்.",
        "hi": "आप क्या जानना चाहेंगे? अपना सवाल लिखें, हम यहीं जवाब देंगे।"},
    "Type your question in a few words.": {"ta": "உங்கள் கேள்வியைச் சில வார்த்தைகளில் தட்டச்சு செய்யுங்கள்.",
                                           "hi": "अपना सवाल कुछ शब्दों में लिखें।"},
    "Thanks — {business} has your question and will reply here.": {
        "ta": "நன்றி — உங்கள் கேள்வி {business}-க்குக் கிடைத்தது; இங்கே பதில் அளிப்பார்கள்.",
        "hi": "धन्यवाद — {business} को आपका सवाल मिल गया है, वे यहीं जवाब देंगे।"},
    # ---------------------------------------------------------------- dues, track, reorder
    "Your account: {amount} due. Details and pay: {link}": {
        "ta": "உங்கள் கணக்கு: {amount} பாக்கி. விவரமும் செலுத்தவும்: {link}",
        "hi": "आपका खाता: {amount} बाकी। विवरण और भुगतान: {link}"},
    "Bill {number}: {amount} — {link}": {"ta": "பில் {number}: {amount} — {link}", "hi": "बिल {number}: {amount} — {link}"},
    "Nothing is due. Thank you!": {"ta": "பாக்கி எதுவும் இல்லை. நன்றி!", "hi": "कुछ भी बाकी नहीं है। धन्यवाद!"},
    "You have no open orders with us. Send menu to order.": {
        "ta": "எங்களிடம் உங்கள் நடப்பு ஆர்டர் எதுவும் இல்லை. ஆர்டர் செய்ய மெனு என்று அனுப்புங்கள்.",
        "hi": "हमारे पास आपका कोई चालू ऑर्डर नहीं है। ऑर्डर करने के लिए मेनू भेजें।"},
    "waiting for the shop to accept": {"ta": "கடை ஏற்கக் காத்திருக்கிறது", "hi": "दुकान की मंज़ूरी का इंतज़ार"},
    "accepted": {"ta": "ஏற்கப்பட்டது", "hi": "मंज़ूर"},
    "being prepared": {"ta": "தயாராகிறது", "hi": "तैयार हो रहा है"},
    "ready": {"ta": "தயார்", "hi": "तैयार"},
    "completed": {"ta": "முடிந்தது", "hi": "पूरा हुआ"},
    "cancelled": {"ta": "ரத்து செய்யப்பட்டது", "hi": "रद्द"},
    "declined": {"ta": "ஏற்கப்படவில்லை", "hi": "अस्वीकार"},
    "The items from your last order are not available now.": {
        "ta": "உங்கள் கடைசி ஆர்டரின் பொருட்கள் இப்போது கிடைக்கவில்லை.",
        "hi": "आपके पिछले ऑर्डर का सामान अभी उपलब्ध नहीं है।"},
    "Your last order ({number}) again, at today's prices:": {
        "ta": "உங்கள் கடைசி ஆர்டர் ({number}) மீண்டும், இன்றைய விலையில்:",
        "hi": "आपका पिछला ऑर्डर ({number}) फिर से, आज के दाम पर:"},
    # ---------------------------------------------------------------- change / cancel
    "Order {number}": {"ta": "ஆர்டர் {number}", "hi": "ऑर्डर {number}"},
    "You have nothing open to change or cancel.": {"ta": "மாற்றவோ ரத்து செய்யவோ எதுவும் இல்லை.",
                                                   "hi": "बदलने या रद्द करने के लिए कुछ भी चालू नहीं है।"},
    "Which one?": {"ta": "எது?", "hi": "कौन सा?"},
    "To change it": {"ta": "மாற்றுவதற்கு", "hi": "बदलने के लिए"},
    "Cancel order {number}?": {"ta": "ஆர்டர் {number}-ஐ ரத்து செய்யவா?", "hi": "ऑर्डर {number} रद्द करें?"},
    "Yes, cancel it": {"ta": "ஆம், ரத்து செய்", "hi": "हाँ, रद्द करें"},
    "Keep it": {"ta": "ரத்து வேண்டாம்", "hi": "रहने दें"},
    "{title} on {when}.": {"ta": "{title} — {when}.", "hi": "{title} — {when}।"},
    "Cancel it": {"ta": "ரத்து செய்", "hi": "रद्द करें"},
    "Book another time": {"ta": "வேறு நேரம் முன்பதிவு", "hi": "दूसरा समय बुक करें"},
    "Order {number} is already {status}, so it can't be cancelled here.": {
        "ta": "ஆர்டர் {number} ஏற்கெனவே {status}, அதனால் இங்கே ரத்து செய்ய முடியாது.",
        "hi": "ऑर्डर {number} पहले ही {status} है, इसलिए यहाँ रद्द नहीं हो सकता।"},
    "It's too close to the day to cancel here ({hours} hours' notice).": {
        "ta": "அந்த நாள் மிக அருகில் உள்ளதால் இங்கே ரத்து செய்ய முடியாது ({hours} மணி நேர முன்னறிவிப்பு தேவை).",
        "hi": "दिन बहुत पास है, इसलिए यहाँ रद्द नहीं हो सकता ({hours} घंटे पहले बताना होता है)।"},
    "Order {number} is cancelled.": {"ta": "ஆர்டர் {number} ரத்து செய்யப்பட்டது.", "hi": "ऑर्डर {number} रद्द हो गया।"},
    "It's too close to the time to cancel here ({hours} hours' notice).": {
        "ta": "நேரம் மிக அருகில் உள்ளதால் இங்கே ரத்து செய்ய முடியாது ({hours} மணி நேர முன்னறிவிப்பு தேவை).",
        "hi": "समय बहुत पास है, इसलिए यहाँ रद्द नहीं हो सकता ({hours} घंटे पहले बताना होता है)।"},
    "Your booking {number} is cancelled.": {"ta": "உங்கள் முன்பதிவு {number} ரத்து செய்யப்பட்டது.",
                                            "hi": "आपकी बुकिंग {number} रद्द हो गई।"},
    # ---------------------------------------------------------------- the router (services/messaging.py)
    "You will not get offers from us on WhatsApp any more. Order and booking updates still come here.": {
        "ta": "இனி WhatsApp-இல் எங்கள் சலுகைகள் வராது. ஆர்டர், முன்பதிவு தகவல்கள் தொடர்ந்து இங்கே வரும்.",
        "hi": "अब आपको WhatsApp पर हमारे ऑफ़र नहीं आएँगे। ऑर्डर और बुकिंग की जानकारी यहीं आती रहेगी।"},
    "Thanks — someone from {business} will reply here soon.": {
        "ta": "நன்றி — {business}-இலிருந்து ஒருவர் விரைவில் இங்கே பதிலளிப்பார்.",
        "hi": "धन्यवाद — {business} से कोई जल्द ही यहाँ जवाब देगा।"},
    "Or send menu to see what you can do here.": {
        "ta": "அல்லது இங்கே என்ன செய்யலாம் என்று பார்க்க மெனு என்று அனுப்புங்கள்.",
        "hi": "या यहाँ क्या-क्या कर सकते हैं, देखने के लिए मेनू भेजें।"},
}

# Shown in every language at once, so anyone can find their own.
LANGUAGE_ROW = ("Language · மொழி · भाषा", "English, தமிழ், हिंदी")
LANGUAGE_ASK = "Which language would you like? · எந்த மொழியில் எழுதலாம்? · आप किस भाषा में बात करना चाहेंगे?"

_DAYS = {"ta": ("திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"),
         "hi": ("सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार")}
_MONTHS = {"ta": ("ஜன", "பிப்", "மார்", "ஏப்", "மே", "ஜூன்", "ஜூலை", "ஆக", "செப்", "அக்", "நவ", "டிச"),
           "hi": ("जन", "फ़र", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अग", "सित", "अक्टू", "नव", "दिस")}


def tr(lang: str | None, text: str, **params: Any) -> str:
    """The phrase in ``lang`` (English when there is no wording), with values filled in."""
    template = text if lang in (None, "en") else PHRASES.get(text, {}).get(lang or "", text)
    return template.format(**params) if params else template


def detect(text: str) -> str | None:
    """Tamil or Hindi when the message is written in its script; None for Latin text."""
    tamil = sum(1 for ch in text if "஀" <= ch <= "௿")
    deva = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    if tamil >= 2 and tamil >= deva:
        return "ta"
    if deva >= 2:
        return "hi"
    return None


def day_words(d: date, lang: str | None) -> str:
    """"Tue 06 Oct" / "செவ்வாய், 6 அக்" / "मंगलवार, 6 अक्टू"."""
    if lang not in ("ta", "hi"):
        return d.strftime("%a %d %b")
    return f"{_DAYS[lang][d.weekday()]}, {d.day} {_MONTHS[lang][d.month - 1]}"


def clock(t: time, lang: str | None) -> str:
    """"5:30 pm" / "மாலை 5:30" / "शाम 5:30"."""
    hour12 = t.hour % 12 or 12
    hm = f"{hour12}:{t.minute:02d}" if t.minute else f"{hour12}"
    if lang == "ta":
        part = "அதிகாலை" if t.hour < 5 else "காலை" if t.hour < 12 else "மதியம்" if t.hour < 16 \
            else "மாலை" if t.hour < 19 else "இரவு"
        return f"{part} {hm}"
    if lang == "hi":
        part = "रात" if t.hour < 4 else "सुबह" if t.hour < 12 else "दोपहर" if t.hour < 16 \
            else "शाम" if t.hour < 20 else "रात"
        return f"{part} {hm}"
    return t.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ").lower()


def when_words(at: datetime, today: date, lang: str | None) -> str:
    """"Tomorrow, 5 pm" in the customer's language."""
    d = at.date()
    day = tr(lang, "Today") if d == today else tr(lang, "Tomorrow") if (d - today).days == 1 else day_words(d, lang)
    return f"{day}, {clock(at.timetz().replace(tzinfo=None), lang)}"
