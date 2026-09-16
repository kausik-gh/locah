"""Canonical business-creation validation constants (Docs 07, 11, 12)."""

from __future__ import annotations

# Doc 12 §11.2 — cannot be Business slugs
RESERVED_SLUGS: frozenset[str] = frozenset(
    {
        "search",
        "auth",
        "activity",
        "api",
        "admin",
        "static",
        "_next",
        "health",
        "webhooks",
        "about",
        "terms",
        "privacy",
        "help",
        "support",
        "blog",
        "pricing",
        "marketplace",
        "app",
        "b",
        "public",
        "sitemap.xml",
        "robots.txt",
    }
)

# First Launch recommendation seeds (Doc 11 §5 / §15) + Other/Not sure (Doc 07 §5.1)
SUPPORTED_BUSINESS_TYPES: frozenset[str] = frozenset(
    {
        "retail",
        "restaurant",
        "cafe",
        "hotel",
        "homestay",
        "salon",
        "spa",
        "gym",
        "studio",
        "clinic",
        "professional_service",
        "education",
        "other",
        "not_sure",
    }
)

# First Launch geography defaults toward India (+91 in Doc 04); ISO 4217 subset
SUPPORTED_CURRENCIES: frozenset[str] = frozenset(
    {"INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD"}
)

# ISO 3166-1 alpha-2 subset used at First Launch
SUPPORTED_COUNTRIES: frozenset[str] = frozenset(
    {"IN", "US", "GB", "AE", "SG", "AU", "CA"}
)

# BCP 47 language tags (dashboard / AI response language seeds)
SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {"en", "hi", "ta", "te", "kn", "ml", "mr", "bn", "gu"}
)

# Common IANA timezones for First Launch; UTC always allowed
SUPPORTED_TIMEZONES: frozenset[str] = frozenset(
    {
        "UTC",
        "Asia/Kolkata",
        "Asia/Dubai",
        "Asia/Singapore",
        "Europe/London",
        "America/New_York",
        "America/Los_Angeles",
        "Australia/Sydney",
    }
)

DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_CURRENCY = "INR"
DEFAULT_COUNTRY = "IN"
DEFAULT_LANGUAGE = "en"
DEFAULT_BUSINESS_TYPE = "not_sure"

DISPLAY_NAME_MIN = 2
DISPLAY_NAME_MAX = 100
SLUG_MIN = 2
SLUG_MAX = 50
