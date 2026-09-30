"""Demo businesses for a LOCAH demonstration — explicit, idempotent, API only.

    # local stack (the acceptance owner's session):
    uv run python tools/demo/seed.py --session acceptance-out/session.json --yes
    # a deployed stack: the demo owner's own access token, from a signed-in browser
    LOCAH_API=https://api.example LOCAH_DEMO_TOKEN=<owner access token> uv run python tools/demo/seed.py --yes

It creates three businesses OWNED BY THE SIGNED-IN DEMO OWNER, through the
same public API the Workspace uses — no database access, no service-role key,
no hidden bypass: it can only do what that owner could do by hand, and it can
never touch anyone else's business. Run it again and it skips a business that
already exists under that name.

  • Demo · Iron Temple Strength (gym)       — plans, members (one paid, one not),
                                              personal training, hours, AI receptionist
  • Demo · Saffron Table (restaurant)       — menu, a recipe that takes paneer off stock,
                                              low-stock threshold, table bookings
  • Demo · Cool Fix Services (field service) — customer, technician, an enquiry, a
                                              quote sent for acceptance

WhatsApp: when the API runs with MESSAGING_SANDBOX=1 each gets the TEST /
SANDBOX number (clearly labelled in the Workspace); otherwise that step is
skipped and reported — nothing pretends to be live.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

API = os.getenv("LOCAH_API", "http://localhost:8010").rstrip("/")
HOURS = {d: [["06:00", "22:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
MEAL_HOURS = {d: [["11:00", "15:00"], ["18:30", "23:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
WORK_HOURS = {d: [["09:00", "19:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat")}


SKIPPED: dict[str, list[str]] = {}


class Api:
    def __init__(self, token: str) -> None:
        self.http = httpx.Client(base_url=API, headers={"Authorization": f"Bearer {token}"}, timeout=60)

    def __call__(self, method: str, path: str, body: Any = None, *, ok: tuple[int, ...] = (200,)) -> Any:
        r = self.http.request(method, path, json=body)
        if r.status_code not in ok:
            raise SystemExit(f"{method} {path} → {r.status_code} {r.text[:300]}")
        return r.json().get("data") if r.content else None


def business(api: Api, name: str, category: str, sub: str, btype: str, modules: list[str]) -> tuple[str, str, bool]:
    """(id, slug, created) — an existing business of this name is reused, not duplicated."""
    for b in api("GET", "/v1/platform/businesses") or []:
        entry = b.get("business", b)
        if entry.get("display_name") == name:
            return str(entry["id"]), str(entry.get("slug") or ""), False
    made = api("POST", "/v1/platform/businesses", {"display_name": name, "business_type": btype,
                                                   "category_key": category, "subcategory_key": sub})["business"]
    bid = str(made["id"])
    for module in modules:
        r = api.http.post(f"/v1/b/{bid}/modules/{module}/enable")
        if r.status_code != 200:
            # e.g. not in this plan: reported, never forced.
            SKIPPED.setdefault(name, []).append(f"{module} ({r.json().get('error', {}).get('code', r.status_code)})")
    return bid, str(made["slug"]), True


def location(api: Api, bid: str, hours: dict[str, Any]) -> str:
    base = f"/v1/platform/businesses/{bid}"
    loc = next(x for x in api("GET", f"{base}/locations") if x["is_primary"])
    api("PATCH", f"{base}/locations/{loc['id']}", {"hours": hours, "phone": "+919840012345"})
    return str(loc["id"])


def whatsapp(api: Api, bid: str, name: str, phone: str) -> str:
    r = api.http.post(f"/v1/platform/businesses/{bid}/messaging/channel/sandbox",
                      json={"display_phone": phone, "display_name": name})
    return "TEST / SANDBOX number connected" if r.status_code == 200 else \
        f"skipped (sandbox off on this API: {r.status_code}) — connect a real number in Workspace › WhatsApp"


def product(api: Api, bid: str, **body: Any) -> str:
    body.setdefault("status", "active")
    body.setdefault("visibility", "public")
    return str(api("POST", f"/v1/platform/businesses/{bid}/products", body)["id"])


def gym(api: Api) -> dict[str, Any]:
    name = "Demo · Iron Temple Strength"
    bid, slug, created = business(api, name, "fitness", "gym", "gym", [
        "offerings-catalog", "memberships", "payments", "customer-relationships", "attendance", "bookings",
        "workforce", "messaging", "leads", "ai-employees"])
    if not created:
        return {"name": name, "id": bid, "slug": slug, "seeded": "already there"}
    base = f"/v1/platform/businesses/{bid}"
    loc = location(api, bid, HOURS)
    monthly = api("POST", f"{base}/membership-plans", {"name": "Monthly", "price_amount": 2500, "duration_days": 30,
                                                       "status": "active", "visibility": "public"})
    api("POST", f"{base}/membership-plans", {"name": "Quarterly", "price_amount": 6500, "duration_days": 90,
                                             "status": "active", "visibility": "public"})
    product(api, bid, title="Personal training session", offering_type="service", price_amount=800,
            attributes={"duration_minutes": 45})
    api("POST", f"{base}/workforce/members", {"display_name": "Coach Karthik", "designation": "Head coach",
                                              "location_ids": [loc]})
    for person, phone, paid in (("Divya R", "+919840061001", True), ("Arjun S", "+919840061002", False)):
        contact = api("POST", f"{base}/customers", {"display_name": person, "phone": phone})
        enrolment = api("POST", f"{base}/membership-enrolments", {
            "plan_id": monthly["id"], "customer_contact_id": contact["id"], "payment_method": "pay_at_business",
            "idempotency_key": str(uuid.uuid4())})
        if paid:
            api("POST", f"{base}/collect/record", {"source_type": "membership", "source_id": enrolment["id"],
                                                   "amount": 2500, "method": "cash"})
    wa = whatsapp(api, bid, "Iron Temple", "+919840070001")
    api("PATCH", f"/v1/b/{bid}/ai-employees/receptionist", {"enabled": True}, ok=(200, 422))
    return {"name": name, "id": bid, "slug": slug, "seeded": "created", "whatsapp": wa}


def restaurant(api: Api) -> dict[str, Any]:
    name = "Demo · Saffron Table"
    bid, slug, created = business(api, name, "food_service", "restaurant", "restaurant", [
        "offerings-catalog", "orders", "inventory", "kitchen", "procurement", "recipes", "payments", "bookings",
        "customer-relationships", "messaging", "reviews", "loyalty", "ai-employees"])
    if not created:
        return {"name": name, "id": bid, "slug": slug, "seeded": "already there"}
    base = f"/v1/platform/businesses/{bid}"
    loc = location(api, bid, MEAL_HOURS)
    wrap = product(api, bid, title="Paneer wrap", offering_type="menu_item", price_amount=180, track_inventory=False)
    for title, price in (("Chicken biryani", 260), ("Veg meals", 150), ("Filter coffee", 40)):
        product(api, bid, title=title, offering_type="menu_item", price_amount=price, track_inventory=False)
    paneer = product(api, bid, title="Paneer", offering_type="product", price_amount=0, track_inventory=True,
                     stock_unit="g", low_stock_threshold=400, visibility="private")
    api("POST", f"{base}/inventory/opening-stock", {"offering_id": paneer, "location_id": loc, "quantity": 1000,
                                                    "reason": "Opening"})
    api("PUT", f"{base}/recipes", {"offering_id": wrap, "name": "Paneer wrap",
                                   "lines": [{"component_offering_id": paneer, "quantity_per": 120}]})
    wa = whatsapp(api, bid, "Saffron Table", "+919840070002")
    return {"name": name, "id": bid, "slug": slug, "seeded": "created", "whatsapp": wa}


def field_service(api: Api) -> dict[str, Any]:
    name = "Demo · Cool Fix Services"
    bid, slug, created = business(api, name, "home_services", "appliance_repair", "professional_service", [
        "offerings-catalog", "quotes", "customer-relationships", "projects", "jobs", "workforce", "leads",
        "invoicing", "payments", "messaging", "ai-employees"])
    if not created:
        return {"name": name, "id": bid, "slug": slug, "seeded": "already there"}
    base = f"/v1/platform/businesses/{bid}"
    loc = location(api, bid, WORK_HOURS)
    product(api, bid, title="Split AC deep service", offering_type="service", price_amount=1200,
            attributes={"duration_minutes": 60})
    api("POST", f"{base}/workforce/members", {"display_name": "Technician Senthil", "designation": "AC technician",
                                              "location_ids": [loc]})
    api("POST", f"{base}/leads", {"display_name": "Meena Apartments", "phone": "+919840061004",
                                  "message": "Need annual maintenance for 12 split ACs", "source": "website_enquiry"})
    client = api("POST", f"{base}/customers", {"display_name": "Ravi Kumar", "phone": "+919840061003"})
    quote = api("POST", f"{base}/quotes", {"title": "AC servicing — 3 units", "customer_contact_id": client["id"],
                                           "items": [{"title": "Split AC deep service", "quantity": 3,
                                                      "unit_price": 1200, "tax_rate": 18}]})
    api("POST", f"{base}/quotes/{quote['id']}/issue", {"valid_days": 10})
    wa = whatsapp(api, bid, "Cool Fix", "+919840070003")
    return {"name": name, "id": bid, "slug": slug, "seeded": "created", "whatsapp": wa}


def main() -> None:
    args = sys.argv[1:]
    if "--yes" not in args:
        raise SystemExit(__doc__)
    token = os.getenv("LOCAH_DEMO_TOKEN", "")
    if "--session" in args:
        token = json.loads(Path(args[args.index("--session") + 1]).read_text())["token"]
    if not token:
        raise SystemExit("Give the demo owner's access token: LOCAH_DEMO_TOKEN=… or --session <file>")
    api = Api(token)
    report = [gym(api), restaurant(api), field_service(api)]
    for entry in report:
        if SKIPPED.get(entry["name"]):
            entry["modules_not_switched_on"] = SKIPPED[entry["name"]]
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
