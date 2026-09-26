"""More owners, for the website fixtures: brands the interview personas don't cover.

Same shape as interview_personas (an opening, answers by ask, the model's
scripted reading of each). Chosen to test the design system where it is
hardest: three meat businesses that must not look alike, and trades whose
look is not their category's default (a calm yoga studio, a playful play
school, a law practice, a cosy café).
"""

from __future__ import annotations

from platform_testing.interview_eval import Persona, intel

PREM = ("The Cleaver Room is a premium butcher on Boat Club Road — dry-aged mutton, free-range chicken and "
        "hand-cut steaks for home chefs. Customers order online and we deliver the same day.")
FAM = ("Selvam Mutton Stall is our family-run mutton shop in Saidapet since 1987. Goat mutton, chicken and "
       "eggs, cut fresh. People walk in or call to keep their order aside.")
APP = ("FreshCut Express is an app-first meat delivery brand in Bengaluru — chicken, mutton and seafood cleaned "
       "and packed, delivered within 60 minutes. Customers order online.")
CAFE = ("Filter & Fold is a cosy filter-coffee cafe in Mylapore — coffee, tiffin and bakes. People walk in, and "
        "groups call to book a table.")
YOGA = ("Still Water Yoga is a calm yoga studio in Besant Nagar — hatha, prenatal yoga and meditation classes. "
        "People book a class online.")
LAW = ("Iyer & Rao Associates is a law firm in Egmore — property law, family disputes and company registration. "
       "Clients call to book a consultation.")
KIDS = ("Little Sprouts is a fun, colourful play school in Anna Nagar for kids aged 2 to 5 — playgroup, nursery "
        "and day care. Parents call to book a visit.")


def _contact(text: str, place: str, phone: str) -> tuple[str, dict[str, object]]:
    said: tuple[str, dict[str, object]] = intel(
        text, facts={"locations": place, "phone": phone},
        answered={"contact.location": place, "contact.phone": phone})
    return said


WEBSITE_PERSONAS: list[Persona] = [
    Persona(
        "premium-butcher", "The Cleaver Room", "Premium butcher", ("fresh_grocery", "butcher", "Butcher"), "retail",
        intel(PREM,
              facts={"offerings": "dry-aged mutton, free-range chicken and hand-cut steaks",
                     "customer_actions": "Customers order online", "locations": "Boat Club Road"},
              answered={"business.identity": "a premium butcher on Boat Club Road",
                        "offerings.main": "dry-aged mutton, free-range chicken and hand-cut steaks",
                        "commerce.action": "Customers order online",
                        "fulfilment.mode": "we deliver the same day"},
              patterns={"product_led": "dry-aged mutton", "order_led": "order online",
                        "local_delivery": "we deliver the same day"},
              catalogue=[{"group": "Mutton", "items": [{"name": "Dry-aged mutton"}]},
                         {"group": "Chicken", "items": [{"name": "Free-range chicken"}]},
                         {"group": "Steaks", "items": [{"name": "Hand-cut steaks"}]}]),
        {"contact": _contact("Boat Club Road, Chennai. 9840011223.", "Boat Club Road, Chennai", "9840011223"),
         "phone": intel("9840011223", facts={"phone": "9840011223"}, answered={"contact.phone": "9840011223"}),
         "area": intel("Across central Chennai.", answered={"fulfilment.area": "central Chennai"})},
        core={"business.identity", "offerings.main", "commerce.action"}, actions={"order_online"},
        tools={"offerings-catalog", "orders"}, follow_ups=(1, 6),
    ),
    Persona(
        "family-butcher", "Selvam Mutton Stall", "Family butcher", ("fresh_grocery", "meat_shop", "Meat shop"),
        "retail",
        intel(FAM,
              facts={"offerings": "Goat mutton, chicken and eggs", "locations": "Saidapet",
                     "customer_actions": "People walk in or call to keep their order aside"},
              answered={"business.identity": "our family-run mutton shop in Saidapet since 1987",
                        "offerings.main": "Goat mutton, chicken and eggs",
                        "commerce.action": "People walk in or call to keep their order aside"},
              patterns={"product_led": "Goat mutton, chicken and eggs", "walk_in": "People walk in"},
              catalogue=[{"group": "Mutton", "items": [{"name": "Goat mutton"}]},
                         {"group": "Chicken"}, {"group": "Eggs"}]),
        {"contact": _contact("Saidapet, Chennai. 9444056789.", "Saidapet, Chennai", "9444056789"),
         "phone": intel("9444056789", facts={"phone": "9444056789"}, answered={"contact.phone": "9444056789"}),
         "fulfilment": intel("No delivery, only from the shop.",
                             answered={"fulfilment.mode": "only from the shop"}, patterns={"pickup": "only from the shop"})},
        core={"business.identity", "offerings.main", "commerce.action"}, actions={"visit", "call", "order_call"},
        tools={"offerings-catalog"}, follow_ups=(1, 6),
    ),
    Persona(
        "meat-delivery-app", "FreshCut Express", "Meat delivery brand", ("fresh_grocery", "meat_shop", "Meat shop"),
        "retail",
        intel(APP,
              facts={"offerings": "chicken, mutton and seafood", "locations": "Bengaluru",
                     "customer_actions": "Customers order online"},
              answered={"business.identity": "an app-first meat delivery brand in Bengaluru",
                        "offerings.main": "chicken, mutton and seafood", "commerce.action": "Customers order online",
                        "fulfilment.mode": "delivered within 60 minutes"},
              patterns={"product_led": "chicken, mutton and seafood", "order_led": "order online",
                        "local_delivery": "delivered within 60 minutes"},
              catalogue=[{"group": "Chicken"}, {"group": "Mutton"}, {"group": "Fish & Seafood"}]),
        {"contact": _contact("HSR Layout, Bengaluru. 9900112233.", "HSR Layout, Bengaluru", "9900112233"),
         "phone": intel("9900112233", facts={"phone": "9900112233"}, answered={"contact.phone": "9900112233"}),
         "area": intel("All over Bengaluru.", answered={"fulfilment.area": "All over Bengaluru"})},
        core={"business.identity", "offerings.main", "commerce.action"}, actions={"order_online"},
        tools={"offerings-catalog", "orders"}, follow_ups=(1, 6),
    ),
    Persona(
        "cafe", "Filter & Fold", "Café", ("food_service", "cafe", "Café"), "cafe",
        intel(CAFE,
              facts={"offerings": "coffee, tiffin and bakes", "locations": "Mylapore",
                     "customer_actions": "People walk in, and groups call to book a table"},
              answered={"business.identity": "a cosy filter-coffee cafe in Mylapore",
                        "offerings.main": "coffee, tiffin and bakes",
                        "commerce.action": "groups call to book a table"},
              patterns={"walk_in": "People walk in"},
              catalogue=[{"group": "Coffee"}, {"group": "Tiffin"}, {"group": "Bakes"}]),
        {"contact": _contact("Mylapore, Chennai. 9840077665.", "Mylapore, Chennai", "9840077665"),
         "phone": intel("9840077665", facts={"phone": "9840077665"}, answered={"contact.phone": "9840077665"})},
        core={"business.identity", "offerings.main"}, actions={"book_call", "visit"}, tools=set(), follow_ups=(1, 6),
    ),
    Persona(
        "yoga-studio", "Still Water Yoga", "Yoga studio", ("fitness", "yoga", "Yoga"), "studio",
        intel(YOGA,
              facts={"offerings": "hatha, prenatal yoga and meditation classes", "locations": "Besant Nagar",
                     "customer_actions": "People book a class online"},
              answered={"business.identity": "a calm yoga studio in Besant Nagar",
                        "offerings.main": "hatha, prenatal yoga and meditation classes",
                        "commerce.action": "People book a class online"},
              patterns={"runs_classes": "meditation classes", "appointment_led": "book a class online"},
              catalogue=[{"group": "Hatha"}, {"group": "Prenatal yoga"}, {"group": "Meditation"}]),
        {"contact": _contact("Besant Nagar, Chennai. 9876001122.", "Besant Nagar, Chennai", "9876001122"),
         "phone": intel("9876001122", facts={"phone": "9876001122"}, answered={"contact.phone": "9876001122"})},
        core={"business.identity", "offerings.main", "commerce.action"}, actions={"book_online"},
        tools={"bookings"}, follow_ups=(1, 6),
    ),
    Persona(
        "law-firm", "Iyer & Rao Associates", "Law practice", ("professional", "lawyer", "Lawyer"),
        "professional_service",
        intel(LAW,
              facts={"offerings": "property law, family disputes and company registration", "locations": "Egmore",
                     "customer_actions": "Clients call to book a consultation"},
              answered={"business.identity": "a law firm in Egmore",
                        "offerings.main": "property law, family disputes and company registration",
                        "commerce.action": "Clients call to book a consultation"},
              patterns={"appointment_led": "book a consultation"},
              catalogue=[{"group": "Property law"}, {"group": "Family disputes"}, {"group": "Company registration"}]),
        {"contact": _contact("Egmore, Chennai. 9840033221.", "Egmore, Chennai", "9840033221"),
         "phone": intel("9840033221", facts={"phone": "9840033221"}, answered={"contact.phone": "9840033221"})},
        core={"business.identity", "offerings.main", "commerce.action"}, actions={"book_call", "book_consultation"},
        tools=set(), follow_ups=(1, 6),
    ),
    Persona(
        "play-school", "Little Sprouts", "Play school", ("education", "preschool", "Preschool"), "education",
        intel(KIDS,
              facts={"offerings": "playgroup, nursery and day care", "locations": "Anna Nagar",
                     "customer_actions": "Parents call to book a visit"},
              answered={"business.identity": "a fun, colourful play school in Anna Nagar",
                        "offerings.main": "playgroup, nursery and day care",
                        "commerce.action": "Parents call to book a visit"},
              catalogue=[{"group": "Playgroup"}, {"group": "Nursery"}, {"group": "Day care"}]),
        {"contact": _contact("Anna Nagar, Chennai. 9791012345.", "Anna Nagar, Chennai", "9791012345"),
         "phone": intel("9791012345", facts={"phone": "9791012345"}, answered={"contact.phone": "9791012345"})},
        core={"business.identity", "offerings.main", "commerce.action"}, actions={"book_call", "visit"},
        tools=set(), follow_ups=(1, 6),
    ),
]
