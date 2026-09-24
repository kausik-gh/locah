"""The canonical taxonomy of what a Business is, for people looking for one.

`business_types.SUPPORTED_BUSINESS_TYPES` is coarse on purpose: it seeds the
modules and the workspace a Business starts with, so "a meat shop", "a
jeweller" and "a pump supplier" can all arrive as `retail` or `other`. That is
right for configuration and useless for discovery — nobody searches for
"retail". This module is the finer, people-facing layer: families a customer
browses ("Fresh Food & Grocery") and the categories inside them ("Meat &
Seafood").

It is the single source for categories. The Marketplace API serves it, the
public web app renders it, and nothing else keeps its own list. A Business is
placed from facts it published — its business type, what it says it does, and
what its published website and catalogue list — never from a guess about
popularity or quality.

Adding a category is a data change here; the Marketplace, its filters, its
counts and its category pages follow without code elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    # Words that, found in what a Business publishes about itself, place it here.
    keywords: tuple[str, ...] = ()
    # Coarse business types that fall here when nothing more specific is said.
    business_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class CategoryFamily:
    id: str
    label: str
    # One line a person reads on the category tile. Plain, no claims.
    blurb: str
    categories: tuple[Category, ...] = field(default_factory=tuple)

    def category(self, category_id: str) -> Category | None:
        return next((c for c in self.categories if c.id == category_id), None)


def _c(cid: str, label: str, keywords: str = "", types: str = "") -> Category:
    return Category(
        id=cid,
        label=label,
        keywords=tuple(k.strip() for k in keywords.split(",") if k.strip()),
        business_types=tuple(t.strip() for t in types.split(",") if t.strip()),
    )


CATEGORY_FAMILIES: tuple[CategoryFamily, ...] = (
    CategoryFamily("food-drink", "Food & Drink", "Restaurants, cafés, home kitchens and caterers", (
        _c("restaurants", "Restaurants", "restaurant, dining, biryani, meals, thali, mess, dhaba, eatery", "restaurant"),
        _c("cafes-bakeries", "Cafés & Bakeries", "cafe, café, coffee, tea, chai, bakery, cakes, cake, pastries, bread, dessert", "cafe"),
        _c("home-kitchens", "Home Kitchens", "home food, homemade, home-made, home kitchen, tiffin, podi, pickle, pickles, thokku"),
        _c("sweets-snacks", "Sweets & Snacks", "sweets, snacks, murukku, laddu, burfi, mithai, namkeen, savouries"),
        _c("catering", "Catering", "catering, caterer, caterers, banquet food, party orders, bulk food"),
    )),
    CategoryFamily("fresh-grocery", "Fresh Food & Grocery", "Meat, fish, vegetables and the daily shop", (
        _c("meat-seafood", "Meat & Seafood", "meat, chicken, mutton, fish, seafood, prawns, crab, squid, butcher, poultry, eggs"),
        _c("fruits-vegetables", "Fruits & Vegetables", "vegetables, fruits, greens, produce, sabzi"),
        _c("grocery", "Grocery & Supermarkets", "grocery, groceries, supermarket, provision, kirana, staples, rice, dal"),
        _c("dairy", "Dairy", "milk, dairy, curd, paneer, ghee, butter"),
        _c("organic", "Organic & Natural", "organic, natural foods, millets, cold pressed"),
    )),
    CategoryFamily("shops", "Shops & Retail", "Everyday stores and specialist shops", (
        _c("general-stores", "General Stores", "store, shop, general store, department store", "retail"),
        _c("electronics", "Electronics & Mobiles", "electronics, mobiles, mobile phones, laptops, appliances, gadgets"),
        _c("furniture-decor", "Furniture & Home Décor", "furniture, sofa, decor, décor, home furnishing, mattress, teak, woodwork"),
        _c("books-stationery", "Books & Stationery", "books, bookstore, stationery, pens, notebooks"),
        _c("flowers-gifts", "Flowers & Gifts", "flowers, florist, bouquet, bouquets, gifts, gift shop, hampers"),
        _c("hardware", "Hardware & Tools", "hardware, tools, paints, sanitaryware, electricals"),
    )),
    CategoryFamily("fashion", "Fashion & Jewellery", "Clothes, tailoring, handloom and jewellery", (
        _c("clothing", "Clothing", "clothing, apparel, garments, boutique, sarees, saree, kurtis, menswear, womenswear"),
        _c("tailoring", "Tailoring", "tailor, tailoring, alterations, stitching, blouse"),
        _c("handloom-textiles", "Handloom & Textiles", "handloom, textiles, fabric, fabrics, weaves, silk, cotton"),
        _c("jewellery", "Jewellery", "jewellery, jewelry, jeweller, gold, silver, diamond, bridal jewellery"),
        _c("footwear", "Footwear & Bags", "footwear, shoes, sandals, chappals, bags"),
    )),
    CategoryFamily("beauty", "Beauty & Grooming", "Salons, spas, barbers and make-up", (
        _c("salons", "Salons", "salon, hair, haircut, hair colour, balayage, beauty parlour, parlour", "salon"),
        _c("spas", "Spa & Massage", "spa, massage, wellness spa, ayurvedic massage", "spa"),
        _c("makeup", "Make-up Artists", "makeup, make-up, bridal makeup, mehendi, mehndi"),
        _c("barbers", "Barbers", "barber, barbershop, shave, beard"),
    )),
    CategoryFamily("fitness", "Fitness & Wellness", "Gyms, yoga, sport and movement", (
        _c("gyms", "Gyms", "gym, fitness, strength, powerlifting, crossfit, weights, training", "gym"),
        _c("yoga-pilates", "Yoga & Pilates", "yoga, pilates, meditation, breathwork", "studio"),
        _c("martial-arts", "Martial Arts & Sports", "martial arts, karate, taekwondo, boxing, kickboxing, sports academy, cricket, football, swimming"),
        _c("wellness", "Wellness Centres", "wellness, naturopathy, nutrition, dietitian"),
    )),
    CategoryFamily("health", "Healthcare", "Clinics, hospitals, dentists and labs", (
        _c("clinics-hospitals", "Clinics & Hospitals", "clinic, hospital, doctor, physician, medical, healthcare, paediatric, gynaecology", "clinic"),
        _c("dental", "Dental", "dental, dentist, teeth, orthodontic, braces, root canal"),
        _c("diagnostics", "Diagnostics & Labs", "diagnostic, diagnostics, lab, laboratory, scan, x-ray, blood test"),
        _c("pharmacy", "Pharmacy", "pharmacy, chemist, medicines, medical store"),
        _c("therapy", "Physio & Therapy", "physiotherapy, physio, therapy, therapist, counselling, speech therapy"),
    )),
    CategoryFamily("learning", "Education & Classes", "Tuition, music, dance, languages and skills", (
        _c("tuition", "Tuition & Coaching", "tuition, tutoring, tutor, tutors, coaching, exam preparation, entrance, neet, jee, board exams, maths, science", "education"),
        _c("music-arts", "Music & Arts", "music, piano, guitar, violin, vocal, carnatic, art classes, drawing, painting"),
        _c("dance", "Dance", "dance, bharatanatyam, classical dance, zumba, choreography"),
        _c("languages", "Languages", "language, spoken english, hindi classes, french, german, ielts"),
        _c("schools", "Schools & Preschools", "school, preschool, play school, montessori, kindergarten"),
        _c("skills", "Skills & Training", "training institute, computer classes, coding classes, skill development"),
    )),
    CategoryFamily("professional", "Professional Services", "Accountants, lawyers, consultants and agencies", (
        _c("accounting", "Accounting & Tax", "accountant, accounting, chartered accountant, ca firm, gst, tax, audit, bookkeeping"),
        _c("legal", "Legal", "lawyer, advocate, legal, law firm, notary"),
        _c("consulting", "Consulting", "consultant, consulting, consultancy, advisory", "professional_service"),
        _c("agencies", "Marketing & Design Agencies", "agency, marketing agency, branding, advertising, digital marketing, design studio"),
    )),
    CategoryFamily("finance", "Finance & Insurance", "Insurance, loans and financial advice", (
        _c("insurance", "Insurance", "insurance, policy, lic"),
        _c("loans-advice", "Loans & Advice", "loans, loan, financial advisor, mutual funds, investment advisor, chit fund"),
    )),
    CategoryFamily("real-estate", "Real Estate", "Developers, projects, brokers and rentals", (
        _c("developers", "Developers & Builders", "developer, builder, builders, apartments, villas, plots, gated community, residential project, projects"),
        _c("brokers", "Brokers & Agents", "real estate agent, broker, brokerage, property dealer"),
        _c("rentals-pg", "Rentals & PG", "rent, rental homes, pg, paying guest, hostel, co-living"),
    )),
    CategoryFamily("build-interiors", "Construction & Interiors", "Interior designers, architects and contractors", (
        _c("interiors", "Interior Design", "interior, interiors, interior designer, modular kitchen, wardrobes"),
        _c("architects", "Architects", "architect, architects, architecture"),
        _c("contractors", "Contractors", "contractor, construction, civil works, renovation"),
        _c("materials", "Building Materials", "tiles, cement, steel, granite, marble, plywood"),
    )),
    CategoryFamily("home-services", "Home Services", "Repairs, cleaning, laundry and upkeep", (
        _c("repairs", "Repairs & AC Service", "repair, repairs, ac service, ac repair, appliance repair, electrician, plumber, plumbing, carpenter"),
        _c("cleaning", "Cleaning & Pest Control", "cleaning, deep cleaning, pest control, housekeeping"),
        _c("laundry", "Laundry & Dry Cleaning", "laundry, dry cleaning, ironing"),
        _c("movers", "Packers & Movers", "packers, movers, relocation, shifting"),
    )),
    CategoryFamily("automotive", "Automotive", "Garages, detailing, dealers and driving schools", (
        _c("detailing", "Car Care & Detailing", "detailing, car wash, ceramic coating, ppf, car care"),
        _c("garages", "Garages & Service", "garage, mechanic, car service, bike service, workshop, tyres"),
        _c("dealers", "Dealers", "car dealer, bike dealer, showroom, used cars"),
        _c("driving-schools", "Driving Schools", "driving school, driving classes"),
    )),
    CategoryFamily("stays-travel", "Travel & Stays", "Hotels, homestays and travel planners", (
        _c("hotels", "Hotels", "hotel, resort, lodge, rooms", "hotel"),
        _c("homestays", "Homestays", "homestay, home stay, guest house, farmstay, bnb", "homestay"),
        _c("travel", "Travel & Tours", "travel agency, tours, tour, holidays, tickets, visa"),
    )),
    CategoryFamily("events", "Events & Celebrations", "Planners, weddings, décor and venues", (
        _c("planners", "Event Planners", "event planner, events, event management, birthday party"),
        _c("weddings", "Weddings", "wedding, weddings, bridal, marriage"),
        _c("decor-venues", "Décor & Venues", "decoration, decorators, venue, hall, mandapam, banquet"),
    )),
    CategoryFamily("creative", "Creative & Media", "Photographers, printers and studios", (
        _c("photography", "Photography & Video", "photographer, photography, videography, photo studio, candid"),
        _c("printing", "Printing", "printing, printers, print shop, flex, visiting cards"),
        _c("artists", "Artists & Makers", "artist, handmade, crafts, pottery, illustrator"),
    )),
    CategoryFamily("technology", "Technology", "Software, IT services and device repair", (
        _c("software", "Software & IT Services", "software, it services, app development, web development, saas"),
        _c("device-repair", "Computer & Phone Repair", "computer repair, laptop repair, phone repair, mobile repair"),
    )),
    CategoryFamily("industrial", "Industrial & Manufacturing", "Manufacturers, machinery and industrial supply", (
        _c("manufacturers", "Manufacturers", "manufacturer, manufacturing, factory, fabrication, machining"),
        _c("machinery", "Machinery & Pumps", "pumps, pump, motors, machinery, compressors, valves"),
        _c("industrial-supply", "Industrial Supplies", "industrial supplies, bearings, fasteners, hoses, fittings, spares"),
    )),
    CategoryFamily("wholesale", "Wholesale & Distribution", "Wholesalers, distributors and traders", (
        _c("wholesalers", "Wholesalers", "wholesale, wholesaler, bulk supply"),
        _c("distributors", "Distributors & Traders", "distributor, distributors, trader, traders, dealership"),
    )),
    CategoryFamily("logistics", "Logistics & Courier", "Couriers, transport and warehousing", (
        _c("courier", "Courier & Delivery", "courier, parcel, delivery service, last mile"),
        _c("transport", "Transport", "transport, trucking, logistics, freight, cargo"),
        _c("warehousing", "Warehousing", "warehouse, warehousing, storage"),
    )),
    CategoryFamily("agriculture", "Agriculture & Farming", "Farms, nurseries and farm supplies", (
        _c("farms", "Farms", "farm, farms, farmer, farm fresh, poultry farm"),
        _c("nurseries", "Nurseries & Plants", "nursery, plants, saplings, gardening, landscaping"),
        _c("farm-supplies", "Farm Supplies", "seeds, fertiliser, fertilizer, pesticides, agri inputs"),
    )),
    CategoryFamily("energy", "Energy & Environment", "Solar, water and recycling", (
        _c("solar", "Solar", "solar, rooftop solar, inverter, batteries"),
        _c("water", "Water & Purifiers", "water purifier, ro, water supply, borewell"),
        _c("recycling", "Recycling & Waste", "recycling, scrap, waste management, compost"),
    )),
    CategoryFamily("pets", "Pets", "Grooming, vets, pet shops and boarding", (
        _c("pet-grooming", "Pet Grooming", "pet grooming, dog grooming, grooming salon, pet spa"),
        _c("vets", "Vets", "vet, veterinary, animal clinic, pet clinic"),
        _c("pet-shops", "Pet Shops & Boarding", "pet shop, pet food, pet boarding, kennel, dog training"),
    )),
    CategoryFamily("rentals", "Rentals", "Equipment, vehicles and things to hire", (
        _c("equipment-rental", "Equipment Rental", "equipment rental, tools on rent, camera rental"),
        _c("vehicle-rental", "Vehicle Rental", "car rental, bike rental, self drive, cabs, taxi"),
        _c("event-rental", "Event Rentals", "tent house, chairs on rent, sound system rental"),
    )),
    CategoryFamily("community", "Community & NGOs", "Non-profits, clubs and places of worship", (
        _c("ngos", "NGOs & Non-profits", "ngo, non-profit, charity, trust, foundation"),
        _c("clubs", "Clubs & Associations", "club, association, society, community centre"),
        _c("worship", "Places of Worship", "temple, church, mosque, gurudwara"),
    )),
)

FAMILIES_BY_ID: dict[str, CategoryFamily] = {f.id: f for f in CATEGORY_FAMILIES}

# The glyph each family is drawn with. Names, not artwork: the public web app
# owns the drawings, this owns which one a family gets.
FAMILY_ICONS: dict[str, str] = {
    "food-drink": "bowl",
    "fresh-grocery": "basket",
    "shops": "storefront",
    "fashion": "hanger",
    "beauty": "scissors",
    "fitness": "dumbbell",
    "health": "cross",
    "learning": "book",
    "professional": "briefcase",
    "finance": "shield",
    "real-estate": "building",
    "build-interiors": "ruler",
    "home-services": "wrench",
    "automotive": "car",
    "stays-travel": "bed",
    "events": "sparkle",
    "creative": "camera",
    "technology": "chip",
    "industrial": "gear",
    "wholesale": "boxes",
    "logistics": "truck",
    "agriculture": "leaf",
    "energy": "sun",
    "pets": "paw",
    "rentals": "key",
    "community": "people",
}

# Coarse business types that say nothing about the kind of business.
_UNINFORMATIVE_TYPES = frozenset({"other", "not_sure", "", None})


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()


def _pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])")


# Precompiled once: classification runs on every re-index.
_KEYWORD_PATTERNS: tuple[tuple[str, str, str, re.Pattern[str], int], ...] = tuple(
    (family.id, category.id, keyword, _pattern(keyword), len(keyword.split()))
    for family in CATEGORY_FAMILIES
    for category in family.categories
    for keyword in category.keywords
)


_QUERY_PATTERNS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = tuple(
    (family.id, category.id, phrase, _pattern(_normalise(phrase)))
    for family in CATEGORY_FAMILIES
    for category in family.categories
    for phrase in (category.label, *category.keywords)
)


@dataclass(frozen=True)
class Placement:
    family_id: str | None
    category_id: str | None
    # Which published words decided it, for anyone asking why a Business sits
    # where it does. Empty when the business type alone decided.
    evidence: tuple[str, ...] = ()


def classify(business_type: str | None, texts: Iterable[str | None]) -> Placement:
    """Place a Business from what it published about itself.

    `texts` are its own public words, most specific first: what its website
    and catalogue list, then its description. Every keyword hit scores its
    category (multi-word phrases score more — "pet grooming" outranks
    "grooming"), and the business type breaks ties or decides alone when the
    words say nothing. A Business that says nothing and is typed `other` is
    left unplaced rather than guessed.
    """
    corpus = _normalise(" \n ".join(t for t in texts if t))
    scores: dict[tuple[str, str], float] = {}
    evidence: dict[tuple[str, str], list[str]] = {}
    if corpus:
        for family_id, category_id, keyword, pattern, words in _KEYWORD_PATTERNS:
            hits = len(pattern.findall(corpus))
            if hits:
                key = (family_id, category_id)
                scores[key] = scores.get(key, 0.0) + min(hits, 3) * (1.0 + 0.6 * (words - 1))
                evidence.setdefault(key, []).append(keyword)

    if business_type not in _UNINFORMATIVE_TYPES:
        for family in CATEGORY_FAMILIES:
            for category in family.categories:
                if business_type in category.business_types:
                    key = (family.id, category.id)
                    # A prior, not a verdict: two words from the owner outweigh it.
                    scores[key] = scores.get(key, 0.0) + 1.5

    if not scores:
        return Placement(None, None)
    (family_id, category_id), _ = max(scores.items(), key=lambda kv: (kv[1], -_order(kv[0])))
    return Placement(family_id, category_id, tuple(evidence.get((family_id, category_id), ())[:5]))


def _order(key: tuple[str, str]) -> int:
    """Stable tie-break: the taxonomy's own order."""
    for index, family in enumerate(CATEGORY_FAMILIES):
        if family.id == key[0]:
            for sub_index, category in enumerate(family.categories):
                if category.id == key[1]:
                    return index * 100 + sub_index
    return 10_000


def search_terms(family_id: str | None, category_id: str | None) -> list[str]:
    """Words a person might type that should find a Business placed here."""
    family = FAMILIES_BY_ID.get(family_id or "")
    if family is None:
        return []
    terms = [family.label]
    category = family.category(category_id or "")
    if category is not None:
        terms.append(category.label)
        terms.extend(category.keywords[:8])
    return terms


def match_query(query: str | None, *, limit: int = 3) -> list[dict[str, str]]:
    """Categories a search names outright ("bakery", "pet grooming", "gym").

    Used to offer a category next to search results, never to replace them:
    the text search still decides what matches. Longest phrase wins, so
    "pet grooming" suggests Pet Grooming rather than Salons.
    """
    text = _normalise(query or "")
    if len(text) < 3:
        return []
    found: dict[tuple[str, str], int] = {}
    for family_id, category_id, phrase, pattern in _QUERY_PATTERNS:
        if pattern.search(text):
            key = (family_id, category_id)
            found[key] = max(found.get(key, 0), len(phrase))
    ranked = sorted(found.items(), key=lambda kv: (-kv[1], _order(kv[0])))
    return [labels(fid, cid) for (fid, cid), _ in ranked[:limit]]  # type: ignore[misc]


def labels(family_id: str | None, category_id: str | None) -> dict[str, str | None]:
    family = FAMILIES_BY_ID.get(family_id or "")
    category = family.category(category_id or "") if family else None
    return {
        "family": family.id if family else None,
        "family_label": family.label if family else None,
        "category": category.id if category else None,
        "category_label": category.label if category else None,
    }


def serialize_taxonomy(counts: dict[tuple[str, str | None], int] | None = None) -> list[dict[str, Any]]:
    """The taxonomy as the public API serves it.

    `counts` maps (family_id, category_id) and (family_id, None) to the number
    of discoverable Businesses placed there. A count is only ever a count of
    real listings; a family with none says so rather than hiding.
    """
    counts = counts or {}
    return [
        {
            "id": family.id,
            "label": family.label,
            "blurb": family.blurb,
            "icon": FAMILY_ICONS.get(family.id, "storefront"),
            "count": counts.get((family.id, None), 0),
            "categories": [
                {
                    "id": category.id,
                    "label": category.label,
                    "count": counts.get((family.id, category.id), 0),
                }
                for category in family.categories
            ],
        }
        for family in CATEGORY_FAMILIES
    ]
