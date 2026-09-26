"""The canonical business taxonomy: 32 categories + Other, their subcategories,
synonyms owners actually type, default operating traits and a playbook key.

Source: LOCAH Business Capability Universe §4 (classification) and §21–§22
(sector playbooks, operating models). This file is the one registry for it
(§4.4); the frontend reads it through `/v1/platform/taxonomy`, nothing is
hard-coded twice.

What a category is for — and what it is not:

* It seeds the interview: which questions an expert in this trade would ask,
  in the trade's own words, and which tools are likely to fit.
* Its traits are **priors**, never facts. "Meat shops usually deliver" makes
  "do you deliver?" worth asking; it never puts "Home delivery" on a website.
  Only what the owner says becomes business truth.
* `template` keeps the legacy `business_type` key the rest of the platform
  still reads (Capability Universe §4.1: `business_type` stays as the website
  template key until the P1 migration).

Search is deterministic and spelling-tolerant: no model call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

TAXONOMY_VERSION = "2026-09-26.1"

# Operating traits (Capability Universe §4.3), as used here.
TRAITS = frozenset({
    # buyer
    "b2c", "b2b",
    # offer
    "sells_products", "sells_services", "sells_access",
    # how they transact
    "order_led", "booking_led", "quote_led", "enquiry_led", "subscription_led", "project_led",
    "donation_led",
    # booking kind
    "appointment", "table", "stay", "class", "rental", "site_visit", "event_date",
    # fulfilment
    "walk_in", "pickup", "local_delivery", "shipping", "on_site_service", "digital",
    # stock
    "weight_based", "made_to_order", "perishable", "variant_based",
    # people
    "provider_based", "field_team",
    # presentation
    "portfolio_led", "nonprofit",
})


@dataclass(frozen=True)
class Subcategory:
    key: str
    label: str
    synonyms: tuple[str, ...]
    traits: frozenset[str]
    playbook: str


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    template: str  # legacy business_type
    tile: bool  # shown as a tile before the owner types anything
    subcategories: tuple[Subcategory, ...]


def _s(key: str, label: str, playbook: str, traits: frozenset[str], *synonyms: str) -> Subcategory:
    unknown = traits - TRAITS
    if unknown:  # pragma: no cover — a typo in this file, caught at import
        raise ValueError(f"unknown traits for {key}: {sorted(unknown)}")
    return Subcategory(key, label, tuple(synonyms), traits, playbook)


def _t(*names: str) -> frozenset[str]:
    return frozenset(names)


# Trait sets shared by many subcategories.
FRESH = _t("b2c", "sells_products", "order_led", "walk_in", "pickup", "local_delivery",
           "weight_based", "perishable")
GROCERY = _t("b2c", "sells_products", "order_led", "walk_in", "pickup", "local_delivery", "variant_based")
HOME_FOOD = _t("b2c", "sells_products", "order_led", "pickup", "local_delivery", "made_to_order",
               "perishable")
SHELF_FOOD = _t("b2c", "sells_products", "order_led", "pickup", "local_delivery", "shipping",
                "made_to_order")
TIFFIN = _t("b2c", "sells_products", "subscription_led", "order_led", "local_delivery", "perishable")
DINE = _t("b2c", "sells_products", "order_led", "booking_led", "table", "walk_in", "pickup",
          "local_delivery")
CAFE = _t("b2c", "sells_products", "order_led", "walk_in", "pickup", "local_delivery")
BAKERY = _t("b2c", "sells_products", "order_led", "walk_in", "pickup", "local_delivery",
            "made_to_order", "perishable")
CATER = _t("b2c", "b2b", "sells_services", "quote_led", "enquiry_led", "event_date", "on_site_service")
SHOP = _t("b2c", "sells_products", "order_led", "walk_in", "pickup", "local_delivery", "variant_based")
SHOP_SHIP = SHOP | _t("shipping")
MADE = _t("b2c", "sells_products", "order_led", "enquiry_led", "made_to_order", "pickup", "shipping")
TAILOR = _t("b2c", "sells_services", "sells_products", "booking_led", "appointment", "made_to_order",
            "walk_in")
UNIFORM = _t("b2b", "sells_products", "quote_led", "made_to_order")
SALON = _t("b2c", "sells_services", "booking_led", "appointment", "walk_in", "provider_based")
ARTIST = _t("b2c", "sells_services", "booking_led", "event_date", "enquiry_led", "portfolio_led",
            "on_site_service")
GYM = _t("b2c", "sells_access", "subscription_led", "booking_led", "class", "walk_in")
STUDIO = _t("b2c", "sells_access", "booking_led", "class", "subscription_led")
COACH = _t("b2c", "sells_services", "booking_led", "appointment", "subscription_led", "digital")
CLINIC = _t("b2c", "sells_services", "booking_led", "appointment", "walk_in", "provider_based")
HOSPITAL = CLINIC
LAB = _t("b2c", "b2b", "sells_services", "booking_led", "appointment", "on_site_service")
PHARMACY = _t("b2c", "sells_products", "order_led", "walk_in", "pickup", "local_delivery")
CARE_HOME = _t("b2c", "sells_services", "enquiry_led", "subscription_led", "on_site_service",
               "field_team")
THERAPY = _t("b2c", "sells_services", "booking_led", "appointment", "provider_based", "digital")
INSTITUTE = _t("b2c", "sells_services", "enquiry_led", "subscription_led", "class")
TUTOR = _t("b2c", "sells_services", "booking_led", "class", "enquiry_led", "digital")
PRO = _t("b2c", "b2b", "sells_services", "enquiry_led", "booking_led", "appointment")
CONSULT = _t("b2b", "sells_services", "enquiry_led", "quote_led", "project_led")
PROPERTY = _t("b2c", "sells_products", "enquiry_led", "booking_led", "site_visit")
PROPERTY_RENT = _t("b2c", "sells_services", "enquiry_led", "subscription_led", "stay")
DESIGN = _t("b2c", "b2b", "sells_services", "enquiry_led", "quote_led", "project_led", "site_visit",
            "portfolio_led")
CONTRACTOR = _t("b2c", "b2b", "sells_services", "quote_led", "project_led", "on_site_service",
                "field_team")
HOME_SERVICE = _t("b2c", "sells_services", "booking_led", "appointment", "on_site_service",
                  "field_team")
REPAIR = _t("b2c", "sells_services", "walk_in", "enquiry_led", "booking_led", "appointment")
LAUNDRY = _t("b2c", "sells_services", "order_led", "pickup", "local_delivery", "walk_in")
DEALER = _t("b2c", "sells_products", "enquiry_led", "booking_led", "site_visit", "walk_in")
GARAGE = _t("b2c", "sells_services", "booking_led", "appointment", "walk_in")
DETAILING = _t("b2c", "sells_services", "booking_led", "appointment", "walk_in", "on_site_service",
               "portfolio_led")
PARTS = _t("b2c", "b2b", "sells_products", "order_led", "walk_in", "pickup", "local_delivery")
RENTAL = _t("b2c", "sells_services", "booking_led", "rental", "pickup", "local_delivery")
FREIGHT = _t("b2b", "b2c", "sells_services", "quote_led", "enquiry_led", "on_site_service")
RIDE = _t("b2c", "sells_services", "booking_led", "on_site_service")
STAY = _t("b2c", "sells_services", "booking_led", "stay")
TOUR = _t("b2c", "sells_services", "enquiry_led", "quote_led", "booking_led", "event_date")
EVENTS = _t("b2c", "b2b", "sells_services", "enquiry_led", "quote_led", "event_date", "project_led",
            "portfolio_led")
HALL = _t("b2c", "sells_services", "booking_led", "event_date", "enquiry_led")
FLORIST = _t("b2c", "sells_products", "order_led", "local_delivery", "pickup", "made_to_order",
             "perishable", "event_date")
PHOTO = _t("b2c", "sells_services", "enquiry_led", "quote_led", "event_date", "portfolio_led")
AGENCY = _t("b2b", "sells_services", "enquiry_led", "quote_led", "project_led", "subscription_led",
            "portfolio_led")
MAKER = _t("b2c", "b2b", "sells_services", "enquiry_led", "quote_led", "portfolio_led", "digital")
CREATOR = _t("b2c", "b2b", "sells_services", "sells_products", "enquiry_led", "digital")
TECH = _t("b2b", "sells_services", "enquiry_led", "quote_led", "project_led", "digital")
SUPPLY = _t("b2b", "sells_products", "quote_led", "enquiry_led", "shipping", "local_delivery")
FACTORY = _t("b2b", "sells_products", "quote_led", "made_to_order", "shipping")
PRINT = _t("b2b", "b2c", "sells_products", "quote_led", "made_to_order", "walk_in", "pickup")
TRADE = _t("b2b", "sells_products", "order_led", "quote_led", "local_delivery", "shipping")
FARM = _t("b2c", "b2b", "sells_products", "order_led", "subscription_led", "pickup", "local_delivery",
          "perishable")
AGRI = _t("b2c", "b2b", "sells_products", "sells_services", "walk_in", "enquiry_led")
ENERGY = _t("b2c", "b2b", "sells_services", "enquiry_led", "quote_led", "project_led", "site_visit",
            "on_site_service")
PET_SHOP = _t("b2c", "sells_products", "order_led", "walk_in", "pickup", "local_delivery")
PET_CARE = _t("b2c", "sells_services", "booking_led", "appointment", "stay")
DAYCARE = _t("b2c", "sells_services", "enquiry_led", "subscription_led", "class")
COWORK = _t("b2b", "b2c", "sells_access", "booking_led", "subscription_led", "rental")
SECURITY = _t("b2b", "sells_services", "quote_led", "enquiry_led", "subscription_led", "field_team",
              "on_site_service")
TESTLAB = _t("b2b", "sells_services", "quote_led", "enquiry_led")
CLUB = _t("b2c", "sells_access", "subscription_led", "booking_led", "event_date")
NGO = _t("b2c", "donation_led", "nonprofit", "enquiry_led")


CATEGORIES: tuple[Category, ...] = (
    Category("fresh_grocery", "Fresh food & grocery", "retail", True, (
        _s("meat_shop", "Meat shop", "meat_seafood", FRESH, "meat", "mutton shop", "meat market", "kasai"),
        _s("butcher", "Butcher", "meat_seafood", FRESH, "butchery", "butcher shop"),
        _s("chicken_shop", "Chicken shop", "meat_seafood", FRESH, "chicken center", "poultry shop",
           "broiler shop", "kozhi kadai", "chicken kadai"),
        _s("seafood", "Seafood shop", "meat_seafood", FRESH, "sea food", "prawns", "crab shop"),
        _s("fish_market", "Fish market", "meat_seafood", FRESH, "fish shop", "fish stall", "meen kadai",
           "fish seller"),
        _s("fruit_shop", "Fruit shop", "produce", FRESH, "fruits", "fruit stall", "fruit seller"),
        _s("vegetable_shop", "Vegetable shop", "produce", FRESH, "vegetables", "veggies", "sabzi",
           "kaikari kadai"),
        _s("organic_produce", "Organic produce", "produce", FRESH | _t("shipping"), "organic store",
           "organic vegetables", "organic farm produce"),
        _s("grocery", "Grocery / kirana", "grocery", GROCERY, "kirana", "kirana store", "grocery store",
           "general store", "provisions", "maligai kadai", "mini mart"),
        _s("supermarket", "Supermarket", "grocery", GROCERY, "super market", "hypermarket", "departmental store"),
        _s("provision_store", "Provision store", "grocery", GROCERY, "provision shop"),
        _s("dry_fruits", "Dry fruits", "grocery", GROCERY | _t("shipping", "weight_based"),
           "dry fruit shop", "nuts", "dryfruits"),
        _s("spices", "Spices", "grocery", GROCERY | _t("shipping", "weight_based"), "masala",
           "spice shop", "masala shop"),
        _s("rice_store", "Rice store", "grocery", GROCERY | _t("weight_based"), "rice mandi",
           "rice shop", "arisi kadai"),
        _s("dairy", "Dairy / milk", "dairy_subscription",
           _t("b2c", "sells_products", "subscription_led", "order_led", "local_delivery", "perishable"),
           "milk", "milk delivery", "dairy shop", "paal", "milk booth"),
        _s("eggs", "Eggs", "dairy_subscription",
           _t("b2c", "b2b", "sells_products", "order_led", "local_delivery", "perishable"),
           "egg shop", "egg supplier", "egg wholesale"),
    )),
    Category("home_food", "Home food & packaged food", "restaurant", True, (
        _s("home_kitchen", "Home kitchen", "home_food", HOME_FOOD, "home food", "homemade food",
           "home cooked food", "veetu saapadu", "home chef", "homemade meals"),
        _s("pickles_podi", "Pickles & podi", "home_food", SHELF_FOOD, "pickles", "podi", "thokku",
           "achar", "oorugai"),
        _s("snacks", "Snacks", "home_food", SHELF_FOOD, "namkeen", "murukku", "homemade snacks"),
        _s("sweets", "Sweets", "home_food", SHELF_FOOD, "mithai", "homemade sweets", "sweet maker"),
        _s("home_bakery", "Home bakery", "bakery_sweets", HOME_FOOD, "home baker", "homemade cakes",
           "cake maker", "home bakes", "custom cakes"),
        _s("tiffin", "Tiffin / meal subscription", "tiffin", TIFFIN, "tiffin service", "dabba",
           "meal subscription", "mess", "lunch box service", "meal plan", "mess service"),
        _s("cloud_kitchen", "Cloud kitchen", "restaurant", CAFE - _t("walk_in"), "cloudkitchen",
           "delivery kitchen", "dark kitchen"),
        _s("chocolates", "Homemade chocolates", "home_food", SHELF_FOOD, "chocolates", "chocolatier"),
        _s("jams_sauces", "Jams & sauces", "home_food", SHELF_FOOD, "jams", "sauces", "preserves"),
        _s("millet_foods", "Millet foods", "home_food", SHELF_FOOD, "millets", "millet snacks",
           "siruthaniyam"),
        _s("healthy_meals", "Healthy meals", "tiffin", TIFFIN, "diet meals", "salad subscription",
           "healthy food"),
    )),
    Category("food_service", "Restaurants, cafés & catering", "restaurant", True, (
        _s("restaurant", "Restaurant", "restaurant", DINE, "hotel (restaurant)", "eatery",
           "family restaurant", "unavagam", "dhaba"),
        _s("cafe", "Café", "cafe", CAFE, "cafe", "coffee shop", "coffee house", "bistro"),
        _s("tea_shop", "Tea shop", "cafe", CAFE, "tea stall", "chai", "tea kadai", "tea stop"),
        _s("juice_bar", "Juice bar", "cafe", CAFE, "juice shop", "juice center", "smoothies"),
        _s("bakery", "Bakery", "bakery_sweets", BAKERY, "bakery shop", "bakers", "cake shop",
           "patisserie"),
        _s("pizzeria", "Pizzeria", "restaurant", DINE, "pizza", "pizza place"),
        _s("fast_food", "Fast food", "restaurant", CAFE, "burgers", "shawarma", "fast food joint",
           "quick service"),
        _s("fine_dining", "Fine dining", "restaurant", DINE, "fine dine", "premium restaurant"),
        _s("food_truck", "Food truck", "cafe", CAFE - _t("local_delivery"), "food cart", "street food"),
        _s("catering", "Catering", "catering", CATER, "caterer", "caterers", "wedding catering",
           "event catering", "samayal"),
        _s("canteen", "Canteen", "catering", CATER | _t("subscription_led"), "office canteen",
           "industrial canteen", "corporate canteen"),
        _s("pub_bar", "Pub / bar", "restaurant", DINE - _t("local_delivery"), "pub", "bar",
           "brewery", "lounge"),
        _s("ice_cream", "Ice cream", "cafe", CAFE, "ice cream parlour", "gelato"),
        _s("desserts", "Desserts", "bakery_sweets", CAFE, "dessert shop", "dessert parlour"),
        _s("biryani_shop", "Biryani shop", "restaurant", DINE, "biryani", "biryani centre"),
        _s("mess", "Mess", "restaurant", DINE - _t("table"), "meals mess", "mess hall"),
    )),
    Category("retail", "Retail stores", "retail", True, (
        _s("clothing", "Clothing store", "fashion_retail", SHOP_SHIP, "clothes", "garments",
           "textiles", "readymade", "apparel", "saree shop", "dress shop"),
        _s("footwear", "Footwear", "fashion_retail", SHOP_SHIP, "shoes", "chappals", "slippers"),
        _s("jewellery", "Jewellery", "jewellery", _t("b2c", "sells_products", "walk_in", "enquiry_led",
           "made_to_order"), "jewelry", "jewellers", "gold shop", "nagai kadai", "silver jewellery"),
        _s("cosmetics", "Cosmetics", "general_retail", SHOP_SHIP, "beauty products", "makeup store"),
        _s("stationery", "Stationery", "general_retail", SHOP, "stationary", "book depot"),
        _s("gifts", "Gifts", "general_retail", SHOP_SHIP, "gift shop", "return gifts", "gift hampers"),
        _s("toys", "Toys", "general_retail", SHOP_SHIP, "toy shop", "toy store"),
        _s("electronics", "Electronics", "electronics", SHOP | _t("booking_led"), "electronics shop",
           "home appliances", "appliance store"),
        _s("mobile_store", "Mobile store", "electronics", SHOP, "mobile shop", "phone shop",
           "mobile accessories"),
        _s("furniture", "Furniture", "furniture_decor", SHOP | _t("made_to_order", "enquiry_led"),
           "furniture shop", "furniture store", "sofas", "wooden furniture"),
        _s("home_decor", "Home decor", "furniture_decor", SHOP_SHIP, "decor", "home furnishing",
           "curtains"),
        _s("kitchenware", "Kitchenware", "general_retail", SHOP_SHIP, "vessels", "utensils",
           "pathiram kadai", "steel vessels"),
        _s("hardware", "Hardware", "general_retail", SHOP | _t("b2b"), "hardware shop", "paints",
           "tools shop", "sanitaryware"),
        _s("sports_goods", "Sports goods", "general_retail", SHOP_SHIP, "sports shop", "gym equipment",
           "fitness equipment"),
        _s("books", "Books", "general_retail", SHOP_SHIP, "bookshop", "book store"),
        _s("optical", "Optical", "optical", SHOP | _t("booking_led", "appointment"), "opticals",
           "spectacles", "eyewear", "optician"),
        _s("pet_supplies", "Pet supplies", "pet_shop", PET_SHOP, "pet food", "pet store"),
    )),
    Category("fashion_custom", "Fashion, tailoring & handmade", "retail", False, (
        _s("boutique", "Boutique", "boutique", MADE | _t("walk_in"), "designer boutique", "ladies boutique"),
        _s("tailor", "Tailor", "tailoring", TAILOR, "tailoring", "stitching", "alterations", "darzi"),
        _s("bridal_wear", "Bridal wear", "boutique", TAILOR | _t("event_date"), "bridal", "wedding wear",
           "bridal blouse"),
        _s("designer_label", "Designer label", "boutique", MADE, "fashion label", "clothing brand"),
        _s("uniform_supplier", "Uniform supplier", "uniform_b2b", UNIFORM, "uniforms", "school uniforms",
           "corporate uniforms"),
        _s("embroidery", "Embroidery", "boutique", MADE | _t("b2b"), "aari work", "embroidery work"),
        _s("custom_tshirts", "Custom T-shirts", "uniform_b2b", MADE | _t("b2b"), "t-shirt printing",
           "custom merchandise"),
        _s("leather_goods", "Leather goods", "handmade", MADE, "leather bags", "leather products"),
        _s("bags", "Bags", "handmade", MADE, "handbags", "bag maker"),
        _s("handmade_crafts", "Handmade crafts", "handmade", MADE, "handicrafts", "crafts", "artisan"),
    )),
    Category("beauty", "Beauty & personal care", "salon", True, (
        _s("salon", "Salon", "salon", SALON, "beauty salon", "unisex salon", "hair salon", "parlour",
           "beauty parlour"),
        _s("barber", "Barber", "salon", SALON, "barber shop", "barbershop", "men's salon", "saloon"),
        _s("spa", "Spa", "spa", SALON, "day spa", "wellness spa"),
        _s("nail_studio", "Nail studio", "salon", SALON, "nail art", "nail salon"),
        _s("makeup_artist", "Makeup artist", "makeup_artist", ARTIST, "mua", "makeup"),
        _s("bridal_makeup", "Bridal makeup", "makeup_artist", ARTIST, "bridal makeup artist"),
        _s("skincare_clinic", "Skincare clinic", "clinic", CLINIC, "skin clinic", "aesthetic clinic"),
        _s("beauty_academy", "Beauty academy", "institute", INSTITUTE, "beauty course", "makeup course"),
        _s("massage_centre", "Massage centre", "spa", SALON, "massage", "ayurvedic massage"),
        _s("tattoo_studio", "Tattoo studio", "makeup_artist", ARTIST - _t("on_site_service") | _t("appointment"),
           "tattoo", "tattoos"),
        _s("piercing_studio", "Piercing studio", "salon", SALON, "piercing"),
    )),
    Category("fitness", "Fitness & wellness", "gym", True, (
        _s("gym", "Gym", "gym", GYM, "fitness centre", "fitness center", "health club", "workout"),
        _s("yoga", "Yoga", "studio", STUDIO, "yoga studio", "yoga classes", "yoga centre"),
        _s("pilates", "Pilates", "studio", STUDIO, "pilates studio"),
        _s("crossfit", "CrossFit", "gym", GYM, "cross fit", "functional training"),
        _s("powerlifting", "Powerlifting", "gym", GYM, "strength gym", "weightlifting", "barbell club"),
        _s("martial_arts", "Martial arts", "studio", STUDIO, "karate", "silambam", "taekwondo",
           "kickboxing", "mma", "kalari"),
        _s("dance_fitness", "Dance fitness", "studio", STUDIO, "zumba", "dance workout"),
        _s("personal_trainer", "Personal trainer", "coach", COACH, "pt", "fitness coach", "trainer"),
        _s("nutrition_coach", "Nutrition coach", "coach", COACH, "dietitian", "nutritionist", "diet coach"),
        _s("meditation_centre", "Meditation centre", "studio", STUDIO, "meditation"),
        _s("wellness_studio", "Wellness studio", "studio", STUDIO, "wellness centre"),
    )),
    Category("healthcare", "Healthcare & clinics", "clinic", True, (
        _s("hospital", "Hospital", "hospital", HOSPITAL, "multispeciality hospital", "nursing home",
           "maruthuvamanai"),
        _s("clinic", "Clinic", "clinic", CLINIC, "doctor", "gp clinic", "medical clinic", "family doctor"),
        _s("polyclinic", "Polyclinic", "clinic", CLINIC, "poly clinic", "multi-speciality clinic"),
        _s("dental", "Dental clinic", "clinic", CLINIC, "dentist", "dental care", "teeth", "orthodontist"),
        _s("physiotherapy", "Physiotherapy", "clinic", CLINIC | _t("subscription_led"), "physio",
           "physiotherapist", "physiotherapy centre", "physiotherapy center", "physio clinic",
           "rehab centre", "sports rehab"),
        _s("diagnostic_centre", "Diagnostic centre", "diagnostics", LAB, "diagnostics", "scan centre",
           "blood test", "lab tests", "pathology lab"),
        _s("pharmacy", "Pharmacy", "pharmacy", PHARMACY, "medical shop", "chemist", "medicals",
           "drug store"),
        _s("eye_clinic", "Eye clinic", "clinic", CLINIC, "eye hospital", "ophthalmologist"),
        _s("ent", "ENT clinic", "clinic", CLINIC, "ent"),
        _s("dermatology", "Dermatology", "clinic", CLINIC, "dermatologist", "skin doctor"),
        _s("paediatrics", "Paediatrics", "clinic", CLINIC, "pediatrician", "child specialist"),
        _s("fertility_clinic", "Fertility clinic", "clinic", CLINIC, "ivf", "fertility centre"),
        _s("home_nursing", "Home nursing", "care_service", CARE_HOME, "nursing care", "home care nurse"),
        _s("ambulance", "Ambulance service", "care_service", CARE_HOME, "ambulance"),
    )),
    Category("therapy", "Therapy & counselling", "clinic", False, (
        _s("psychologist", "Psychologist", "therapy", THERAPY, "psychology"),
        _s("counsellor", "Counsellor", "therapy", THERAPY, "counselling", "counseling"),
        _s("therapist", "Therapist", "therapy", THERAPY, "therapy"),
        _s("speech_therapy", "Speech therapy", "therapy", THERAPY, "speech therapist"),
        _s("occupational_therapy", "Occupational therapy", "therapy", THERAPY, "ot"),
        _s("rehab_centre", "Rehabilitation centre", "therapy", THERAPY | _t("stay"), "rehab", "de-addiction"),
    )),
    Category("education", "Education & tutoring", "education", True, (
        _s("school", "School", "school", INSTITUTE, "cbse school", "matriculation school"),
        _s("preschool", "Preschool", "school", INSTITUTE, "play school", "kindergarten", "nursery school"),
        _s("tuition_centre", "Tuition centre", "tuition", INSTITUTE, "tuition", "tuitions",
           "tuition classes", "coaching centre"),
        _s("coaching", "Coaching (NEET / JEE)", "tuition", INSTITUTE, "neet coaching", "jee coaching",
           "competitive exams", "tnpsc coaching", "upsc coaching"),
        _s("language_school", "Language school", "tuition", INSTITUTE, "spoken english", "german classes",
           "hindi classes"),
        _s("music_school", "Music school", "arts_school", INSTITUTE, "music classes", "carnatic music",
           "keyboard classes", "guitar classes"),
        _s("dance_school", "Dance school", "arts_school", INSTITUTE, "dance classes", "bharatanatyam"),
        _s("coding_academy", "Coding academy", "tuition", INSTITUTE | _t("digital"), "coding classes",
           "programming classes"),
        _s("vocational_institute", "Vocational institute", "tuition", INSTITUTE, "iti", "skill training"),
        _s("driving_school", "Driving school", "tuition", INSTITUTE | _t("booking_led"), "driving classes",
           "driving training"),
        _s("tutor", "Individual tutor", "tutor", TUTOR, "home tutor", "maths tutor", "ielts tutor",
           "private tutor", "online tutor"),
        _s("online_educator", "Online educator", "creator", CREATOR, "online courses", "course seller"),
    )),
    Category("professional", "Professional & consulting services", "professional_service", False, (
        _s("ca", "Chartered accountant", "professional_firm", PRO | _t("subscription_led"), "ca firm",
           "auditor", "chartered accountants"),
        _s("accountant", "Accountant", "professional_firm", PRO | _t("subscription_led"), "accounting",
           "bookkeeping", "gst filing", "tax filing"),
        _s("lawyer", "Lawyer", "professional_firm", PRO, "advocate", "law firm", "legal services", "vakil"),
        _s("company_secretary", "Company secretary", "professional_firm", PRO, "cs firm"),
        _s("tax_consultant", "Tax consultant", "professional_firm", PRO, "income tax consultant", "itr filing"),
        _s("consultant", "Management / HR consultant", "consulting", CONSULT, "business consultant",
           "hr consultant", "management consultant"),
        _s("recruitment", "Recruitment agency", "consulting", CONSULT, "placement agency", "manpower consultancy"),
        _s("engineering_consultancy", "Engineering / ISO consultancy", "consulting", CONSULT,
           "iso consultant", "quality consultant", "process consultant"),
    )),
    Category("finance_insurance", "Finance & insurance", "professional_service", False, (
        _s("financial_adviser", "Financial adviser", "finance", PRO, "financial advisor",
           "financial planner", "mutual fund distributor"),
        _s("insurance_agent", "Insurance agent", "finance", PRO, "lic agent", "insurance advisor"),
        _s("loan_consultant", "Loan consultant", "finance", PRO, "loan agent", "home loans"),
        _s("wealth_manager", "Wealth manager", "finance", PRO, "wealth management"),
    )),
    Category("real_estate", "Real estate & property", "professional_service", True, (
        _s("developer", "Property developer", "real_estate_developer", PROPERTY, "builder", "builders",
           "promoters", "construction company", "apartment projects", "villa projects"),
        _s("plots", "Plots & layouts", "real_estate_developer", PROPERTY, "plot", "land", "layout",
           "dtcp plots", "plotted development"),
        _s("broker", "Real estate broker", "real_estate_broker", PROPERTY, "real estate agent",
           "property dealer", "estate agent", "realtor", "real estate agency"),
        _s("rental_agency", "Rental agency", "real_estate_broker", PROPERTY_RENT, "house rentals",
           "rental homes"),
        _s("property_management", "Property management", "real_estate_broker", PROPERTY_RENT,
           "facility rentals"),
        _s("co_living", "Co-living / PG", "stay", PROPERTY_RENT, "pg", "paying guest", "hostel for working",
           "co living"),
        _s("commercial_real_estate", "Commercial real estate", "real_estate_broker", PROPERTY | _t("b2b"),
           "office space", "commercial property"),
    )),
    Category("design_build", "Architecture, interiors & construction", "professional_service", True, (
        _s("architect", "Architect", "design_studio", DESIGN, "architecture firm", "architects"),
        _s("interior_designer", "Interior designer", "design_studio", DESIGN, "interiors", "interior design",
           "home interiors", "interior decorator"),
        _s("landscape_architect", "Landscape architect", "design_studio", DESIGN, "landscaping",
           "garden design"),
        _s("modular_kitchen", "Modular kitchens", "design_studio", DESIGN | _t("sells_products"),
           "modular kitchen", "wardrobes"),
        _s("renovation", "Renovation", "contractor", CONTRACTOR, "home renovation", "remodelling"),
        _s("civil_contractor", "Civil contractor", "contractor", CONTRACTOR, "construction contractor",
           "building contractor"),
        _s("electrical_contractor", "Electrical contractor", "contractor", CONTRACTOR, "electrical works"),
        _s("plumbing_contractor", "Plumbing contractor", "contractor", CONTRACTOR, "plumbing works"),
        _s("painting_contractor", "Painting contractor", "contractor", CONTRACTOR, "painters", "painting works"),
        _s("fabrication", "Fabrication", "contractor", CONTRACTOR, "steel fabrication", "welding works"),
        _s("waterproofing", "Waterproofing", "contractor", CONTRACTOR, "leak repair"),
        _s("hvac", "HVAC contractor", "contractor", CONTRACTOR, "ac installation", "ducting"),
    )),
    Category("home_services", "Home, repair & IT services", "professional_service", True, (
        _s("cleaning", "Cleaning service", "home_service", HOME_SERVICE, "home cleaning", "deep cleaning",
           "housekeeping"),
        _s("pest_control", "Pest control", "home_service", HOME_SERVICE, "termite control"),
        _s("plumber", "Plumber", "home_service", HOME_SERVICE, "plumbing"),
        _s("electrician", "Electrician", "home_service", HOME_SERVICE, "electrical repair"),
        _s("appliance_repair", "Appliance repair", "home_service", HOME_SERVICE, "washing machine repair",
           "fridge repair"),
        _s("ac_service", "AC service", "home_service", HOME_SERVICE | _t("subscription_led"), "ac repair",
           "ac servicing"),
        _s("water_purifier", "Water purifier service", "home_service", HOME_SERVICE, "ro service", "ro repair"),
        _s("laundry", "Laundry", "laundry", LAUNDRY, "laundromat", "washing and ironing", "ironing"),
        _s("dry_cleaning", "Dry cleaning", "laundry", LAUNDRY, "dry cleaners"),
        _s("gardening", "Gardening", "home_service", HOME_SERVICE, "gardener", "garden maintenance"),
        _s("repair_shop", "Repair shop", "repair", REPAIR, "watch repair", "shoe repair", "furniture repair"),
        _s("mobile_repair", "Mobile repair", "repair", REPAIR, "phone repair", "mobile service centre"),
        _s("computer_repair", "Computer repair", "repair", REPAIR, "laptop repair", "computer service"),
        _s("cctv", "CCTV installer", "home_service", HOME_SERVICE | _t("quote_led", "b2b"), "cctv",
           "security cameras"),
        _s("networking", "Networking / IT support", "home_service", HOME_SERVICE | _t("b2b"), "it support",
           "networking services"),
    )),
    Category("automotive", "Automotive", "retail", False, (
        _s("car_dealer", "Car dealer", "vehicle_dealer", DEALER, "car showroom", "car sales"),
        _s("used_cars", "Used cars", "vehicle_dealer", DEALER, "second hand cars", "pre-owned cars"),
        _s("bike_dealer", "Bike dealer", "vehicle_dealer", DEALER, "two wheeler showroom", "bike showroom"),
        _s("garage", "Garage / mechanic", "auto_service", GARAGE, "mechanic", "car service",
           "bike service", "workshop", "service centre"),
        _s("car_wash", "Car wash", "auto_service", GARAGE, "car washing", "bike wash"),
        _s("detailing", "Car detailing", "detailing", DETAILING, "detailing studio", "ceramic coating",
           "ppf", "car spa"),
        _s("tyres", "Tyres", "auto_parts", PARTS, "tyre shop", "tyre dealer", "wheel alignment"),
        _s("batteries", "Batteries", "auto_parts", PARTS, "battery shop", "inverter batteries"),
        _s("spare_parts", "Spare parts", "auto_parts", PARTS, "auto parts", "car accessories"),
        _s("car_rental", "Car rental", "rentals", RENTAL, "self drive cars", "car hire"),
        _s("driver_service", "Driver service", "rentals", RIDE, "acting drivers", "call driver"),
    )),
    Category("logistics", "Transport, logistics & storage", "professional_service", False, (
        _s("courier", "Courier", "logistics", FREIGHT, "courier service", "parcel service"),
        _s("packers_movers", "Packers & movers", "logistics", FREIGHT | _t("b2c"), "movers",
           "house shifting", "relocation"),
        _s("trucking", "Trucking", "logistics", FREIGHT, "lorry service", "transport company",
           "truck booking", "transporters"),
        _s("fleet_operator", "Fleet operator", "logistics", FREIGHT, "fleet"),
        _s("last_mile", "Last-mile delivery", "logistics", FREIGHT, "delivery company", "hyperlocal delivery"),
        _s("warehousing", "Warehousing", "logistics", FREIGHT - _t("on_site_service"), "warehouse",
           "godown", "storage"),
        _s("cold_storage", "Cold storage", "logistics", FREIGHT - _t("on_site_service"), "cold chain"),
        _s("freight_forwarding", "Freight forwarding", "logistics", FREIGHT, "freight forwarder",
           "customs clearance", "cha"),
        _s("taxi", "Taxi service", "rentals", RIDE, "cab service", "taxi", "call taxi", "travels"),
        _s("bus_operator", "Bus operator", "rentals", RIDE, "bus service", "omni bus"),
    )),
    Category("travel_stay", "Travel, stays & tourism", "hotel", True, (
        _s("hotel", "Hotel", "hotel", STAY | _t("walk_in"), "lodge", "hotel rooms", "business hotel"),
        _s("resort", "Resort", "hotel", STAY, "resorts", "farm stay resort"),
        _s("homestay", "Homestay", "homestay", STAY, "home stay", "bnb", "b&b", "cottage"),
        _s("hostel", "Hostel", "homestay", STAY, "backpackers hostel"),
        _s("villa_rental", "Villa rental", "homestay", STAY, "villa", "holiday home"),
        _s("travel_agency", "Travel agency", "travel", TOUR, "travels", "tours and travels", "ticketing"),
        _s("tour_operator", "Tour operator", "travel", TOUR, "tour packages", "holiday packages"),
        _s("adventure_tourism", "Adventure tourism", "travel", TOUR, "trekking", "adventure tours"),
        _s("guide", "Tour guide", "travel", TOUR, "local guide"),
        _s("pilgrimage_tours", "Pilgrimage tours", "travel", TOUR, "yatra", "temple tours"),
    )),
    Category("events", "Events & weddings", "professional_service", True, (
        _s("event_planner", "Event planner", "event_planner", EVENTS, "event management", "event organiser"),
        _s("wedding_planner", "Wedding planner", "event_planner", EVENTS, "wedding management",
           "wedding organiser"),
        _s("decorator", "Decorator", "event_planner", EVENTS, "event decor", "wedding decoration",
           "balloon decoration", "stage decoration"),
        _s("banquet_hall", "Mandapam / banquet hall", "banquet_hall", HALL, "mandapam", "marriage hall",
           "kalyana mandapam", "banquet", "party hall", "convention centre"),
        _s("florist", "Florist", "florist", FLORIST, "flower shop", "flowers", "bouquets", "poo kadai",
           "flower decoration"),
        _s("event_caterer", "Caterer", "catering", CATER, "caterer for events"),
        _s("dj", "DJ", "event_planner", EVENTS - _t("portfolio_led"), "dj services"),
        _s("sound_light_rental", "Sound & light rental", "rentals", RENTAL | _t("event_date"),
           "sound system rental", "lights rental"),
        _s("invitations", "Invitation business", "print_shop", PRINT, "wedding cards", "invitation cards"),
    )),
    Category("creative", "Photography, media & creative", "professional_service", True, (
        _s("wedding_photographer", "Wedding photographer", "photographer", PHOTO, "wedding photography",
           "candid photographer", "wedding shoots"),
        _s("studio_photographer", "Studio photographer", "photographer", PHOTO | _t("walk_in", "appointment"),
           "photo studio", "portrait studio"),
        _s("product_photographer", "Product photographer", "photographer", PHOTO | _t("b2b"),
           "product photography", "ecommerce photography"),
        _s("videographer", "Videographer", "photographer", PHOTO, "video production", "wedding films"),
        _s("filmmaker", "Filmmaker", "photographer", PHOTO | _t("b2b"), "film production", "ad films"),
        _s("drone", "Drone operator", "photographer", PHOTO, "drone shoots"),
        _s("ad_agency", "Ad / digital marketing agency", "creative_agency", AGENCY, "digital marketing",
           "seo agency", "social media agency", "advertising agency", "marketing agency"),
        _s("branding", "Branding studio", "creative_agency", AGENCY, "branding agency", "brand design"),
        _s("pr", "PR agency", "creative_agency", AGENCY, "public relations"),
        _s("content_studio", "Content studio", "creative_agency", AGENCY, "content creation"),
        _s("graphic_designer", "Graphic designer", "maker", MAKER, "logo designer", "designer"),
        _s("illustrator", "Illustrator / artist", "maker", MAKER, "artist", "painter", "illustrations",
           "commission art"),
        _s("ux_designer", "UX designer", "maker", MAKER, "ui designer", "product designer"),
        _s("writer", "Writer", "maker", MAKER, "copywriter", "content writer"),
        _s("musician", "Musician", "maker", MAKER | _t("event_date"), "singer", "band", "live music"),
    )),
    Category("creators", "Creators & personal brands", "professional_service", False, (
        _s("youtuber", "YouTuber / influencer", "creator", CREATOR, "influencer", "content creator",
           "instagrammer"),
        _s("coach", "Coach / speaker", "coach", COACH | _t("event_date"), "life coach", "business coach",
           "motivational speaker", "speaker"),
        _s("author", "Author", "creator", CREATOR, "writer (books)"),
        _s("podcaster", "Podcaster", "creator", CREATOR, "podcast"),
    )),
    Category("technology", "Technology & IT services", "professional_service", False, (
        _s("software_company", "Software company", "software", TECH, "software development",
           "it company", "software services"),
        _s("saas", "SaaS product", "software", TECH | _t("subscription_led", "b2c"), "saas",
           "software product", "app company", "mobile app", "gym app", "fitness app", "tracking app",
           "an app"),
        _s("web_development", "Web / app development", "software", TECH, "website design",
           "web design", "app development"),
        _s("cybersecurity", "Cybersecurity", "software", TECH, "security audit"),
        _s("cloud_data_ai", "Cloud / data / AI consultancy", "software", TECH, "ai consultancy",
           "data analytics", "cloud consulting"),
    )),
    Category("industrial", "Manufacturing & industrial supply", "retail", True, (
        _s("industrial_supplier", "Industrial supplier", "industrial_supplier", SUPPLY,
           "industrial supplies", "pumps", "valves", "motors", "bearings", "instrumentation",
           "safety equipment", "lab equipment", "automation", "machine tools", "pump supplier"),
        _s("chemicals", "Chemicals", "industrial_supplier", SUPPLY, "chemical supplier", "industrial chemicals"),
        _s("manufacturer", "Manufacturer", "manufacturer", FACTORY, "manufacturing", "factory",
           "garment manufacturer", "food manufacturer", "plastics", "auto components"),
        _s("metal_fabrication", "Metal fabrication", "manufacturer", FACTORY, "sheet metal", "cnc machining",
           "machining", "engineering works"),
        _s("process_equipment", "Process equipment / OEM", "manufacturer", FACTORY | _t("project_led"),
           "boilers", "compressors", "conveyors", "water treatment plants"),
        _s("packaging", "Packaging", "manufacturer", FACTORY, "corrugated boxes", "cartons", "labels",
           "packaging materials"),
        _s("printing", "Printing & signage", "print_shop", PRINT, "printing press", "digital printing",
           "flex printing", "signage", "sign boards", "laser cutting"),
    )),
    Category("trade", "Wholesale, distribution & import/export", "retail", False, (
        _s("distributor", "Distributor", "wholesale", TRADE, "distribution", "stockist",
           "dealer (wholesale)", "fmcg distributor", "super stockist"),
        _s("wholesaler", "Wholesaler", "wholesale", TRADE, "wholesale", "wholesale shop", "mandi"),
        _s("exporter", "Exporter", "wholesale", TRADE - _t("local_delivery"), "export house",
           "export", "garment exporter"),
        _s("importer", "Importer / trading company", "wholesale", TRADE, "trading company", "import"),
    )),
    Category("agriculture", "Agriculture & agri services", "retail", False, (
        _s("farm", "Farm", "farm", FARM, "farm fresh", "organic farm", "farmer"),
        _s("nursery", "Plant nursery", "farm", FARM - _t("subscription_led"), "plants", "nursery garden",
           "saplings"),
        _s("dairy_farm", "Dairy farm", "dairy_subscription", FARM, "cow farm", "a2 milk"),
        _s("poultry_farm", "Poultry farm", "farm", FARM | _t("b2b"), "poultry"),
        _s("fish_farm", "Fish farm", "farm", FARM, "aquaculture"),
        _s("mushroom_farm", "Mushroom farm", "farm", FARM, "mushrooms"),
        _s("agri_inputs", "Seeds, fertiliser & agri inputs", "agri_dealer", AGRI, "seeds", "fertiliser",
           "fertilizer", "pesticides", "agri shop"),
        _s("tractor_rental", "Tractor rental", "rentals", RENTAL | _t("on_site_service"), "tractor hire"),
    )),
    Category("energy_env", "Energy & environment", "professional_service", False, (
        _s("solar", "Solar installer", "energy", ENERGY, "solar panels", "solar epc", "rooftop solar"),
        _s("ev_charging", "EV charging", "energy", ENERGY, "ev chargers"),
        _s("generator_rental", "Generator rental", "rentals", RENTAL | _t("b2b"), "genset rental", "dg rental"),
        _s("waste_management", "Waste management", "energy", ENERGY | _t("subscription_led"),
           "recycling", "scrap", "composting"),
        _s("water_treatment", "Water treatment", "energy", ENERGY, "stp", "etp", "ro plants"),
    )),
    Category("pets", "Pets", "retail", False, (
        _s("pet_shop", "Pet shop", "pet_shop", PET_SHOP, "pet store", "aquarium shop", "pet food shop"),
        _s("grooming", "Pet grooming", "pet_care", PET_CARE, "dog grooming", "pet salon"),
        _s("boarding", "Pet boarding", "pet_care", PET_CARE, "dog boarding", "pet hostel"),
        _s("veterinary", "Veterinary clinic", "clinic", CLINIC, "vet", "vet clinic", "pet clinic",
           "animal hospital"),
        _s("pet_training", "Pet training", "pet_care", PET_CARE, "dog training", "dog trainer"),
        _s("dog_walking", "Dog walking", "pet_care", PET_CARE | _t("on_site_service"), "dog walker"),
    )),
    Category("care", "Child, family & senior care", "education", False, (
        _s("daycare", "Daycare", "daycare", DAYCARE, "creche", "day care", "baby care"),
        _s("activity_centre", "Activity centre", "daycare", DAYCARE, "kids activities", "summer camp",
           "hobby classes"),
        _s("kids_sports", "Kids sports", "daycare", DAYCARE, "football academy", "cricket academy",
           "swimming classes", "sports academy"),
        _s("elder_care", "Elder care", "care_service", CARE_HOME | _t("stay"), "old age home",
           "senior living", "assisted living"),
        _s("caregiver_agency", "Caregiver agency", "care_service", CARE_HOME, "caretakers", "nanny agency"),
    )),
    Category("rentals_spaces", "Rentals & spaces", "retail", False, (
        _s("vehicle_rental", "Bike / car rental", "rentals", RENTAL, "bike rental", "bike on rent", "scooter rental"),
        _s("camera_rental", "Camera & equipment rental", "rentals", RENTAL, "camera rental", "lens rental",
           "equipment rental"),
        _s("party_rental", "Party & furniture rental", "rentals", RENTAL | _t("event_date"),
           "party equipment", "chairs rental", "shamiana", "tent house"),
        _s("costume_rental", "Costume & dress rental", "rentals", RENTAL, "dress rental", "costume hire"),
        _s("coworking", "Co-working", "coworking", COWORK, "co working", "shared office", "hot desk"),
        _s("meeting_rooms", "Meeting rooms", "coworking", COWORK, "conference room", "training hall"),
        _s("self_storage", "Self-storage", "coworking", COWORK - _t("booking_led"), "storage units"),
    )),
    Category("security_staffing", "Security, facilities & staffing", "professional_service", False, (
        _s("security_agency", "Security agency", "security_facility", SECURITY, "security guards",
           "security services"),
        _s("fire_safety", "Fire safety", "security_facility", SECURITY, "fire extinguishers", "fire alarm"),
        _s("facility_management", "Facility management", "security_facility", SECURITY,
           "housekeeping contract", "commercial cleaning", "maintenance contracts"),
        _s("manpower", "Manpower supply", "security_facility", SECURITY, "manpower", "staffing",
           "temp staffing", "domestic help agency"),
    )),
    Category("labs", "Testing, research & labs", "professional_service", False, (
        _s("testing_lab", "Testing lab", "testing_lab", TESTLAB, "testing laboratory", "material testing",
           "water testing", "food testing"),
        _s("calibration_lab", "Calibration lab", "testing_lab", TESTLAB, "calibration"),
        _s("research", "R&D / contract research", "testing_lab", TESTLAB, "cro", "research lab"),
        _s("inspection", "Inspection agency", "testing_lab", TESTLAB, "third party inspection"),
    )),
    Category("community", "Clubs, communities & nonprofits", "other", False, (
        _s("club", "Club / association", "community", CLUB, "sports club", "association", "rotary",
           "chamber of commerce"),
        _s("temple_trust", "Temple / trust", "community", NGO | _t("booking_led", "event_date"),
           "temple", "trust", "kovil", "seva"),
        _s("cultural_centre", "Cultural centre", "community", CLUB, "sabha", "community hall"),
        _s("ngo", "NGO / charity", "ngo", NGO, "non profit", "nonprofit", "charity", "foundation",
           "animal rescue"),
    )),
    Category("other", "Something else", "other", False, (
        _s("other", "Something else", "other", _t(), "not sure", "other"),
    )),
)

CATEGORIES_BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}
SUBCATEGORIES: dict[str, tuple[Category, Subcategory]] = {
    s.key: (c, s) for c in CATEGORIES for s in c.subcategories
}


def _norm(text: str) -> str:
    text = re.sub(r"[^a-z0-9\s&/+-]", " ", (text or "").casefold())
    text = re.sub(r"\s*[/&+-]\s*", " ", text)
    return " ".join(text.split())


@lru_cache(maxsize=1)
def _index() -> tuple[tuple[str, str, int], ...]:
    """(phrase, subcategory key, weight) for every label and synonym."""
    rows: list[tuple[str, str, int]] = []
    for category in CATEGORIES:
        for sub in category.subcategories:
            rows.append((_norm(sub.label), sub.key, 3))
            rows.extend((_norm(s), sub.key, 2) for s in sub.synonyms)
            rows.append((_norm(category.label), sub.key, 0))
    return tuple(rows)


def _score(query: str, phrase: str) -> float:
    if not phrase:
        return 0.0
    if query == phrase:
        return 1.0
    words = query.split()
    phrase_words = phrase.split()
    ratio = SequenceMatcher(None, query, phrase).ratio()
    scores = [0.0]
    if phrase.startswith(query) and len(query) >= 3:
        scores.append(0.93)
    if all(any(pw.startswith(w) for pw in phrase_words) for w in words) and len(query) >= 3:
        scores.append(0.88)
    if any(w == pw for w in words for pw in phrase_words if len(w) >= 4):
        overlap = sum(1 for w in words if w in phrase_words) / max(len(phrase_words), len(words))
        scores.append(0.6 + 0.3 * overlap)
    # Spelling tolerance ("dentel clinic", "kirane", "biriyani"), word by word,
    # so "meat shop" is not a near-miss of "tea shop".
    if len(words) == len(phrase_words):
        pairs = [SequenceMatcher(None, w, pw).ratio() for w, pw in zip(words, phrase_words)]
        if min(pairs) >= 0.75:
            scores.append(sum(pairs) / len(pairs))
    best_word = max(
        (SequenceMatcher(None, w, pw).ratio() for w in words for pw in phrase_words if len(w) >= 4),
        default=0.0,
    )
    if best_word >= 0.84:
        scores.append(0.7 * best_word)
    # Closeness of the whole phrase breaks ties between equal heuristics:
    # "meat shop" is nearer "chicken shop" than "biryani shop".
    return max(scores) + (0.04 * ratio if max(scores) else 0.0)


def search(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Subcategories matching what the owner typed, best first. Deterministic."""
    q = _norm(query)
    if len(q) < 2:
        return []
    best: dict[str, float] = {}
    for phrase, key, weight in _index():
        score = _score(q, phrase)
        if score <= 0:
            continue
        score += weight * 0.01
        if score > best.get(key, 0.0):
            best[key] = score
    ranked = sorted(best.items(), key=lambda kv: (-round(kv[1], 4), _ORDER[kv[0]]))
    strong = [key for key, score in ranked if score >= 0.85]
    if not strong:
        return [describe(key) for key, score in ranked[:limit] if score >= 0.6]
    # After the clear matches, the neighbours an owner would also recognise:
    # "meat shop" offers butcher and chicken shop before "tea shop".
    siblings = [s.key for s in SUBCATEGORIES[strong[0]][0].subcategories if s.key not in strong]
    weaker = [key for key, score in ranked if 0.6 <= score < 0.85 and key not in siblings]
    return [describe(key) for key in (strong + siblings + weaker)[:limit]]


# Declared order: when a query only matches a category's name, its
# subcategories come back in the order the registry lists them.
_ORDER: dict[str, int] = {key: index for index, key in enumerate(SUBCATEGORIES)}


def describe(subcategory_key: str) -> dict[str, Any]:
    category, sub = SUBCATEGORIES[subcategory_key]
    return {
        "category_key": category.key,
        "category_label": category.label,
        "subcategory_key": sub.key,
        "subcategory_label": sub.label,
        "template": category.template,
        "playbook": sub.playbook,
    }


def tiles() -> list[dict[str, str]]:
    """The categories shown before the owner types anything."""
    return [{"category_key": c.key, "label": c.label} for c in CATEGORIES if c.tile]


def catalogue() -> dict[str, Any]:
    """Everything the picker needs, from this one registry."""
    return {
        "version": TAXONOMY_VERSION,
        "tiles": tiles(),
        "categories": [
            {
                "key": c.key,
                "label": c.label,
                "subcategories": [{"key": s.key, "label": s.label} for s in c.subcategories],
            }
            for c in CATEGORIES
        ],
    }


def resolve(category_key: str | None, subcategory_key: str | None) -> tuple[Category, Subcategory] | None:
    """A validated (category, subcategory) pair, or None."""
    if subcategory_key and subcategory_key in SUBCATEGORIES:
        category, sub = SUBCATEGORIES[subcategory_key]
        if category_key and category_key != category.key:
            return None
        return category, sub
    if category_key and category_key in CATEGORIES_BY_KEY and not subcategory_key:
        category = CATEGORIES_BY_KEY[category_key]
        # A category alone says less than any of its subcategories: its most
        # common playbook as the seed, and no trait priors at all.
        playbooks = [s.playbook for s in category.subcategories]
        seed = max(set(playbooks), key=playbooks.count)
        return category, Subcategory(key=category.key, label=category.label, synonyms=(),
                                     traits=frozenset(), playbook=seed)
    return None


def _singular(text: str) -> str:
    """"wedding photographers" reads as "wedding photographer"; "glass" stays."""
    return " ".join(w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w
                    for w in text.split())


# What an owner *does* sometimes names the kind of business better than any
# noun they use: "we build villas" is a developer, not a villa rental; "we sell
# chicken, mutton and seafood" is a meat shop. Each is only a prior, shown as
# "Looks like…" and corrected with one tap — never a fact on the website.
_DOING: tuple[tuple[re.Pattern[str], str, float], ...] = (
    (re.compile(r"\b(?:sell|selling|sold|supply)\w*\b[^.]{0,50}\b(?:chicken|mutton|seafood|prawns?|"
                r"fish|meat|crabs?|squid)\b", re.I), "meat_shop", 0.78),
    (re.compile(r"\b(?:chicken|mutton|seafood|meat)\b[^.]{0,40}\b(?:by (?:the )?kg|per kg|kilo)", re.I),
     "meat_shop", 0.78),
    (re.compile(r"\b(?:builds?|building|construct\w*|develop\w*)\b[^.]{0,30}\b(?:villas?|apartments?|"
                r"flats?|homes|houses|gated communit\w*)\b", re.I), "developer", 0.82),
    (re.compile(r"\b(?:sell|selling)\b[^.]{0,30}\b(?:plots?|layouts?)\b", re.I), "plots", 0.8),
    (re.compile(r"\b(?:supply|supplies|supplying|manufactur\w*)\b[^.]{0,60}\b(?:factories|industr\w*|"
                r"plants?|oems?|fasteners|valves|bearings|pipes|fittings)\b", re.I), "industrial_supplier", 0.8),
)
# "…a physiotherapy centre with a small gym": what comes after "with a small"
# is the lesser part of the business.
_SECONDARY = re.compile(r"\b(?:with|and|plus|also)\s+(?:a\s+|an\s+)?(?:small|little|tiny)?\s*$")
# A word used for HOW they work, not WHAT they are: "we courier them" is a
# pickle maker that ships, not a courier company.
_MEANS: dict[str, re.Pattern[str]] = {
    # "book a site visit" is a verb, not a bookshop.
    "books": re.compile(r"\bbook(?:s|ed|ing)?\s+(?:a|an|the|your|their|our|now|online|appointments?|slots?|"
                        r"tables?|trials?|site|visits?|sessions?|classes|rooms?|dates?|tickets?)\b", re.I),
    "taxi": re.compile(r"\bwe travel\b|\btravel (?:anywhere|across|all over)", re.I),
    "courier": re.compile(r"\b(?:by|via|through)\s+courier|\bcouriers?\s+(?:them|it|across|to|all|"
                          r"everywhere|anywhere|orders?)\b|\b(?:and|we)\s+courier\b", re.I),
}


def infer_from_text(text: str) -> tuple[str, float] | None:
    """The subcategory an owner's own words most clearly name, with a confidence.

    Used only as a seed when the owner did not pick one — never shown as fact.
    Whole-phrase matches only, so "customers" never reads as "custom".
    """
    haystack = f" {_singular(_norm(text))} "
    if len(haystack) < 4:
        return None
    best: tuple[str, float] | None = None
    for phrase, key, weight in _index():
        if weight == 0 or len(phrase) < 3:
            continue
        at = haystack.find(f" {_singular(phrase)} ")
        means = _MEANS.get(key)
        if at >= 0 and not (means and means.search(text or "")):
            # The longer phrase is the more specific reading: "gym app" is a
            # software business, not a gym. Between equals, the first said.
            score = 0.6 + 0.08 * len(phrase.split()) + weight * 0.03
            if _SECONDARY.search(haystack[:at + 1]):
                score -= 0.12
            if best is None or score > best[1]:
                best = (key, score)
    for pattern, key, confidence in _DOING:
        if pattern.search(text or "") and (best is None or confidence > best[1]):
            best = (key, confidence)
    if best is None:
        # Tamil script is not in the latin index: a few trade words an owner
        # writing Tamil actually uses.
        for word, key in _TAMIL_TRADES:
            if word in (text or ""):
                return key, 0.76
    return best


_TAMIL_TRADES: tuple[tuple[str, str], ...] = (
    ("சலூன்", "salon"), ("பியூட்டி பார்லர்", "salon"), ("ஜிம்", "gym"),
    ("கறிக்கடை", "meat_shop"), ("இறைச்சி", "meat_shop"), ("மீன் கடை", "fish_market"),
    ("உணவகம்", "restaurant"), ("ஹோட்டல்", "restaurant"), ("பேக்கரி", "bakery"),
    ("மருத்துவமனை", "hospital"), ("கிளினிக்", "clinic"), ("டியூஷன்", "tuition_centre"),
    ("தையல்", "tailor"), ("மளிகை", "grocery"), ("ஊறுகாய்", "pickles_podi"),
)
