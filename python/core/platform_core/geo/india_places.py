"""Indian towns and cities, for ordering listings by where people are.

Reference data, not geocoding: each entry is a place name, its state and the
approximate centre of the town. It lets the Marketplace do two honest things
without calling a map service:

* read "Nookampalayam Road, Chennai" from a published contact section and
  file the Business under Chennai, and
* turn a visitor's rounded coordinates into "near Chennai".

A town centre is good enough to put Chennai listings before Coimbatore ones.
It is never good enough to print "2 km away" — only coordinates the owner set
(`geo_precision = 'exact'`) may be shown as a distance.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Place:
    city: str
    state: str
    lat: float
    lng: float
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedPlace:
    city: str
    state: str
    lat: float
    lng: float
    # The part of the address before the town, as the owner wrote it.
    locality: str | None = None


def _p(city: str, state: str, lat: float, lng: float, *aliases: str) -> Place:
    return Place(city, state, lat, lng, aliases)


PLACES: tuple[Place, ...] = (
    # Tamil Nadu and Puducherry
    _p("Chennai", "Tamil Nadu", 13.083, 80.270, "Madras"),
    _p("Tambaram", "Tamil Nadu", 12.925, 80.127),
    _p("Coimbatore", "Tamil Nadu", 11.017, 76.956, "Kovai"),
    _p("Madurai", "Tamil Nadu", 9.925, 78.120),
    _p("Tiruchirappalli", "Tamil Nadu", 10.790, 78.705, "Trichy", "Tiruchi"),
    _p("Salem", "Tamil Nadu", 11.665, 78.146),
    _p("Tiruppur", "Tamil Nadu", 11.108, 77.341, "Tirupur"),
    _p("Erode", "Tamil Nadu", 11.341, 77.717),
    _p("Vellore", "Tamil Nadu", 12.916, 79.132),
    _p("Thanjavur", "Tamil Nadu", 10.787, 79.138, "Tanjore"),
    _p("Tirunelveli", "Tamil Nadu", 8.713, 77.757),
    _p("Thoothukudi", "Tamil Nadu", 8.764, 78.135, "Tuticorin"),
    _p("Hosur", "Tamil Nadu", 12.740, 77.825),
    _p("Kanchipuram", "Tamil Nadu", 12.834, 79.703, "Kancheepuram"),
    _p("Nagercoil", "Tamil Nadu", 8.178, 77.412),
    _p("Kanyakumari", "Tamil Nadu", 8.078, 77.541),
    _p("Kumbakonam", "Tamil Nadu", 10.960, 79.385),
    _p("Karur", "Tamil Nadu", 10.960, 78.077),
    _p("Dindigul", "Tamil Nadu", 10.365, 77.980),
    _p("Pollachi", "Tamil Nadu", 10.659, 77.009),
    _p("Ooty", "Tamil Nadu", 11.410, 76.695, "Udhagamandalam", "Ootacamund"),
    _p("Kodaikanal", "Tamil Nadu", 10.238, 77.489),
    _p("Puducherry", "Puducherry", 11.934, 79.830, "Pondicherry", "Pondy"),
    # Karnataka
    _p("Bengaluru", "Karnataka", 12.972, 77.594, "Bangalore"),
    _p("Mysuru", "Karnataka", 12.296, 76.639, "Mysore"),
    _p("Mangaluru", "Karnataka", 12.914, 74.856, "Mangalore"),
    _p("Hubballi", "Karnataka", 15.365, 75.124, "Hubli"),
    _p("Belagavi", "Karnataka", 15.850, 74.498, "Belgaum"),
    _p("Udupi", "Karnataka", 13.341, 74.747),
    # Telangana and Andhra Pradesh
    _p("Hyderabad", "Telangana", 17.385, 78.487),
    _p("Secunderabad", "Telangana", 17.440, 78.498),
    _p("Warangal", "Telangana", 17.969, 79.594),
    _p("Visakhapatnam", "Andhra Pradesh", 17.687, 83.219, "Vizag"),
    _p("Vijayawada", "Andhra Pradesh", 16.506, 80.648),
    _p("Guntur", "Andhra Pradesh", 16.307, 80.437),
    _p("Tirupati", "Andhra Pradesh", 13.629, 79.419),
    _p("Nellore", "Andhra Pradesh", 14.443, 79.987),
    # Kerala
    _p("Kochi", "Kerala", 9.931, 76.267, "Cochin", "Ernakulam"),
    _p("Thiruvananthapuram", "Kerala", 8.524, 76.936, "Trivandrum"),
    _p("Kozhikode", "Kerala", 11.259, 75.780, "Calicut"),
    _p("Thrissur", "Kerala", 10.527, 76.214, "Trichur"),
    _p("Kannur", "Kerala", 11.874, 75.370),
    _p("Kollam", "Kerala", 8.893, 76.614),
    # Maharashtra and Goa
    _p("Mumbai", "Maharashtra", 19.076, 72.878, "Bombay"),
    _p("Navi Mumbai", "Maharashtra", 19.033, 73.030),
    _p("Thane", "Maharashtra", 19.218, 72.978),
    _p("Pune", "Maharashtra", 18.520, 73.857),
    _p("Nagpur", "Maharashtra", 21.146, 79.088),
    _p("Nashik", "Maharashtra", 19.998, 73.790),
    _p("Chhatrapati Sambhajinagar", "Maharashtra", 19.876, 75.343, "Aurangabad"),
    _p("Kolhapur", "Maharashtra", 16.705, 74.243),
    _p("Solapur", "Maharashtra", 17.660, 75.906),
    _p("Panaji", "Goa", 15.491, 73.828, "Panjim"),
    _p("Margao", "Goa", 15.274, 73.958, "Madgaon"),
    # North
    _p("Delhi", "Delhi", 28.614, 77.209, "New Delhi"),
    _p("Gurugram", "Haryana", 28.459, 77.027, "Gurgaon"),
    _p("Faridabad", "Haryana", 28.408, 77.317),
    _p("Noida", "Uttar Pradesh", 28.535, 77.391),
    _p("Ghaziabad", "Uttar Pradesh", 28.669, 77.454),
    _p("Chandigarh", "Chandigarh", 30.733, 76.779),
    _p("Mohali", "Punjab", 30.704, 76.717),
    _p("Ludhiana", "Punjab", 30.901, 75.857),
    _p("Amritsar", "Punjab", 31.634, 74.872),
    _p("Jalandhar", "Punjab", 31.326, 75.576),
    _p("Jaipur", "Rajasthan", 26.912, 75.787),
    _p("Jodhpur", "Rajasthan", 26.238, 73.024),
    _p("Udaipur", "Rajasthan", 24.585, 73.712),
    _p("Kota", "Rajasthan", 25.213, 75.865),
    _p("Ajmer", "Rajasthan", 26.450, 74.640),
    _p("Lucknow", "Uttar Pradesh", 26.847, 80.947),
    _p("Kanpur", "Uttar Pradesh", 26.450, 80.332),
    _p("Varanasi", "Uttar Pradesh", 25.318, 82.974, "Banaras", "Benares"),
    _p("Agra", "Uttar Pradesh", 27.177, 78.008),
    _p("Prayagraj", "Uttar Pradesh", 25.436, 81.846, "Allahabad"),
    _p("Meerut", "Uttar Pradesh", 28.984, 77.706),
    _p("Dehradun", "Uttarakhand", 30.317, 78.032),
    _p("Haridwar", "Uttarakhand", 29.946, 78.164),
    _p("Rishikesh", "Uttarakhand", 30.087, 78.268),
    _p("Shimla", "Himachal Pradesh", 31.105, 77.173),
    _p("Srinagar", "Jammu and Kashmir", 34.084, 74.797),
    _p("Jammu", "Jammu and Kashmir", 32.727, 74.857),
    # West and Central
    _p("Ahmedabad", "Gujarat", 23.023, 72.571),
    _p("Surat", "Gujarat", 21.170, 72.831),
    _p("Vadodara", "Gujarat", 22.307, 73.181, "Baroda"),
    _p("Rajkot", "Gujarat", 22.303, 70.802),
    _p("Gandhinagar", "Gujarat", 23.216, 72.637),
    _p("Bhopal", "Madhya Pradesh", 23.260, 77.413),
    _p("Indore", "Madhya Pradesh", 22.720, 75.858),
    _p("Gwalior", "Madhya Pradesh", 26.218, 78.183),
    _p("Jabalpur", "Madhya Pradesh", 23.181, 79.987),
    _p("Raipur", "Chhattisgarh", 21.251, 81.630),
    # East and North-East
    _p("Kolkata", "West Bengal", 22.573, 88.364, "Calcutta"),
    _p("Howrah", "West Bengal", 22.596, 88.264),
    _p("Siliguri", "West Bengal", 26.727, 88.395),
    _p("Durgapur", "West Bengal", 23.520, 87.312),
    _p("Patna", "Bihar", 25.594, 85.138),
    _p("Ranchi", "Jharkhand", 23.344, 85.310),
    _p("Jamshedpur", "Jharkhand", 22.805, 86.203),
    _p("Bhubaneswar", "Odisha", 20.296, 85.825),
    _p("Cuttack", "Odisha", 20.463, 85.883),
    _p("Guwahati", "Assam", 26.144, 91.736),
    _p("Shillong", "Meghalaya", 25.578, 91.893),
)


# The first three digits of a PIN name a sorting district. Only prefixes that
# belong to one town unambiguously are listed; any other PIN still matches
# listings that published that exact PIN, it just cannot be placed on a map.
PIN_PREFIXES: dict[str, str] = {
    "600": "Chennai", "641": "Coimbatore", "625": "Madurai", "620": "Tiruchirappalli",
    "636": "Salem", "638": "Erode", "632": "Vellore", "627": "Tirunelveli",
    "605": "Puducherry", "560": "Bengaluru", "570": "Mysuru", "575": "Mangaluru",
    "500": "Hyderabad", "530": "Visakhapatnam", "520": "Vijayawada", "517": "Tirupati",
    "682": "Kochi", "695": "Thiruvananthapuram", "673": "Kozhikode", "680": "Thrissur",
    "400": "Mumbai", "411": "Pune", "440": "Nagpur", "422": "Nashik",
    "403": "Panaji", "110": "Delhi", "122": "Gurugram", "121": "Faridabad",
    "160": "Chandigarh", "141": "Ludhiana", "143": "Amritsar", "302": "Jaipur",
    "342": "Jodhpur", "313": "Udaipur", "226": "Lucknow", "208": "Kanpur",
    "221": "Varanasi", "282": "Agra", "248": "Dehradun", "380": "Ahmedabad",
    "395": "Surat", "390": "Vadodara", "360": "Rajkot", "462": "Bhopal",
    "452": "Indore", "492": "Raipur", "700": "Kolkata", "800": "Patna",
    "834": "Ranchi", "751": "Bhubaneswar", "781": "Guwahati",
}


_LEAD_IN = re.compile(
    r"^(?:(?:our|my)\s+(?:home|house|place|shop|kitchen|studio|store|office)\s+)?(?:is\s+)?(?:in|at)\s+",
    re.IGNORECASE,
)
_LANDMARK = re.compile(r"^(?:near|opp\.?|opposite|behind|next to|beside)\b", re.IGNORECASE)


def _word(name: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z])" + re.escape(name.lower()) + r"(?![a-z])")


_NAME_PATTERNS: tuple[tuple[Place, str, re.Pattern[str]], ...] = tuple(
    (place, name, _word(name))
    for place in PLACES
    for name in (place.city, *place.aliases)
)


def place_from_address(text: str | None) -> ResolvedPlace | None:
    """The town named in an address, and the locality written before it.

    The last-mentioned town wins ("Anna Nagar, near Madurai Road, Chennai" is
    in Chennai). Returns None when no known town is named — unknown stays
    unknown.
    """
    if not text or not text.strip():
        return None
    lowered = text.lower()
    best: tuple[int, Place, str] | None = None
    for place, name, pattern in _NAME_PATTERNS:
        for match in pattern.finditer(lowered):
            if best is None or match.start() > best[0]:
                best = (match.start(), place, name)
    if best is None:
        return None
    start, place, _ = best
    before = text[:start].strip(" ,-\n")
    parts = [p.strip() for p in before.split(",") if p.strip()] if before else []
    # "Anna Nagar, near Madurai Road": a landmark, not the locality.
    while len(parts) > 1 and _LANDMARK.match(parts[-1]):
        parts.pop()
    locality = parts[-1] if parts else None
    if locality:
        # "Our home in Saibaba Colony" is an address written as a sentence;
        # the locality is the part after "in".
        locality = _LEAD_IN.sub("", locality).strip(" ,-") or None
    if locality and (len(locality) < 3 or locality.isdigit()):
        locality = None
    return ResolvedPlace(place.city, place.state, place.lat, place.lng, locality or None)


def place_by_name(name: str | None) -> Place | None:
    if not name:
        return None
    lowered = name.strip().lower()
    for place, alias, _ in _NAME_PATTERNS:
        if alias.lower() == lowered:
            return place
    return None


def place_from_pin(pin: str | None) -> Place | None:
    digits = re.sub(r"\D", "", pin or "")
    if len(digits) != 6:
        return None
    return place_by_name(PIN_PREFIXES.get(digits[:3]))


def suggest_places(prefix: str | None, *, limit: int = 8) -> list[Place]:
    """Towns whose name or alias starts with what the visitor typed."""
    typed = (prefix or "").strip().lower()
    if len(typed) < 2:
        return []
    seen: list[Place] = []
    for place, alias, _ in _NAME_PATTERNS:
        if alias.lower().startswith(typed) and place not in seen:
            seen.append(place)
        if len(seen) >= limit:
            break
    return seen


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance; plenty precise for ordering a list."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def nearest_place(lat: float, lng: float, *, within_km: float = 60.0) -> Place | None:
    """The town a visitor's rounded coordinates fall in, if any is close."""
    best: tuple[float, Place] | None = None
    for place in PLACES:
        d = distance_km(lat, lng, place.lat, place.lng)
        if best is None or d < best[0]:
            best = (d, place)
    if best is None or best[0] > within_km:
        return None
    return best[1]
