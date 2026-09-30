"""Website v4 — the activation check, with REAL Gemini. No stand-in pixels.

    GEMINI_API_KEY=… IMAGE_PROVIDER=gemini GEMINI_IMAGE_MODEL=<current> \\
      uv run python tools/acceptance/stack/gemini_verify_v4.py acceptance-out/gemini [--local-storage]

It refuses to start without a key, and reports exactly what is missing.

What it runs, all through the product's own API and worker job, against a
LOCAL database (tools/acceptance/stack/db.sh):

1. The config: the key works and the configured GEMINI_IMAGE_MODEL is in
   Google's model list.
2. Five owners (home food, gym, real estate, meat, industrial B2B) talk to
   LOCAH (the real Gemini conversation model), upload nothing, and Build; the
   real website.generate job runs (real creative plan, real images).
3. For each hero: returned by Gemini, persisted as a MediaAsset, assigned to
   the MediaPlan "hero" slot, rendered in the draft (preview) and after
   Publish, marked gemini_generated / draft, and replaceable, removable and
   approvable through the editor's own endpoints.
4. The editor's manual controls on the home-food site: Generate a picture →
   Generate a new picture → Keep this picture → Remove → Upload my photo, and
   one card picture.
5. An owner who uploads their own hero keeps it.
6. A menu PDF read by real Gemini document extraction: every item and price
   it returns must be printed in the PDF.

Storage: with SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY the pictures go to real
Supabase Storage. With --local-storage (no Supabase project here) the SAME
Gemini bytes are written to <out>/media and served by
`python -m http.server 8899 -d <out>/media`; the report says which was used.

Then screenshot the published pages (1440 and 390) with:
    node tools/acceptance/owner_sites.mjs <out>

--self-test replaces Gemini with labelled plates only to prove this harness
itself runs; its report can never mark anything verified.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SELF_TEST = "--self-test" in sys.argv
LOCAL_STORAGE = "--local-storage" in sys.argv or SELF_TEST
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(ARGS[0] if ARGS else "acceptance-out/gemini").resolve()
MEDIA = OUT / "media"
MEDIA_URL = os.getenv("LOCAH_V4_MEDIA_URL", "http://localhost:8899")
DB = os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@localhost:54329/locah_accept")
if "@localhost:" not in DB and "@127.0.0.1:" not in DB:
    sys.exit("local databases only")


def missing_config() -> list[str]:
    missing = []
    if not os.getenv("GEMINI_API_KEY", "").strip():
        missing.append("GEMINI_API_KEY (a Google AI Studio / Gemini API key, server-side)")
    if (os.getenv("IMAGE_PROVIDER") or "gemini").strip().lower() != "gemini":
        missing.append("IMAGE_PROVIDER=gemini")
    if (os.getenv("AI_PROVIDER") or "gemini").strip().lower() != "gemini":
        missing.append("AI_PROVIDER=gemini (or unset)")
    if os.getenv("LOCAH_TEST_NO_EXTERNAL_AI"):
        missing.append("LOCAH_TEST_NO_EXTERNAL_AI must be unset (it refuses every paid call)")
    if not LOCAL_STORAGE and not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")):
        missing.append("SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY for real Storage — or pass --local-storage")
    return missing


if not SELF_TEST:
    problems = missing_config()
    if problems:
        print("NOT RUN — real Gemini cannot run. Missing:\n  - " + "\n  - ".join(problems))
        sys.exit(2)

os.environ["API_DATABASE_URL"] = DB
os.environ["SUPABASE_JWT_SECRET"] = "local-acceptance-secret-with-at-least-32-characters"
os.environ["WEBSITE_PREVIEW_SECRET"] = "local-preview-secret-with-at-least-32-characters"
os.environ["RATE_LIMIT_ENABLED"] = "0"
os.environ["LOCAH_JOBS_INERT"] = "1"
if SELF_TEST:
    os.environ["LOCAH_TEST_NO_EXTERNAL_AI"] = "1"
for key in ("SUPABASE_JWKS_URL",) + (("SUPABASE_URL",) if LOCAL_STORAGE else ()):
    os.environ.pop(key, None)

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

GOLDEN = ("home-food", "gym", "real-estate", "meat-shop", "industrial")
NOT_SURE = "Not sure about that — you decide."
MENU = [("Tiffin", [("Idli (2 pcs)", "40"), ("Ghee Roast Dosa", "90"), ("Pongal", "60")]),
        ("Meals", [("Veg Meals", "150"), ("Chicken Biryani", "220")]),
        ("Podi & Pickles", [("Idli Podi 200 g", "120"), ("Mango Pickle 250 g", "140")])]


# ---------------------------------------------------------------- plumbing

def sql(query: str, **params: Any) -> list[Any]:
    from platform_testing.phase_b import sql as run

    rows: list[Any] = run(query, **params)
    return rows


def local_storage(calls: dict[str, int]) -> None:
    """The same bytes, kept on disk instead of Supabase (reported as such)."""
    import platform_core.media.supabase_storage as storage

    async def put(*, storage_key: str, body: bytes, **_: Any) -> None:
        path = MEDIA / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        calls["stored"] = calls.get("stored", 0) + 1

    storage.put_generated_object = put
    storage.public_url = lambda bucket, key: f"{MEDIA_URL}/{key}"


def count_gemini_images(calls: dict[str, int]) -> None:
    """Count what Gemini itself returned (or, in --self-test, stand in for it)."""
    import platform_core.interview.media_director as md
    import platform_core.services.website_images as wi
    import platform_core.website.image_generation as images

    real = images.generate_image

    async def counted(prompt: str, **kw: Any) -> Any:
        if SELF_TEST:
            from owner_flow_v4 import plate

            image = images.GeneratedImage(mime_type="image/jpeg", bytes=plate(prompt, kw.get("aspect_ratio", "16:9")),
                                          model="SELF-TEST", latency_ms=1, prompt=prompt)
            result: Any = (image, "")
        else:
            result = await real(prompt, **kw)
        if result[0] is not None:
            calls["gemini_images"] = calls.get("gemini_images", 0) + 1
            calls.setdefault("models", 0)
            MODELS.add(str(result[0].model))
        return result

    async def counted_bytes(prompt: str, aspect_ratio: str = "16:9", **kw: Any) -> Any:
        image, _ = await counted(prompt, aspect_ratio=aspect_ratio, **kw)
        return image

    if SELF_TEST:
        images.image_generation_available = lambda: True
    md.generate_image = counted
    wi.generate_image_bytes = counted_bytes


MODELS: set[str] = set()


async def check_model() -> dict[str, Any]:
    """The key works and the configured image model exists."""
    import httpx

    from platform_core.website.image_generation import image_model

    wanted = image_model()
    if SELF_TEST:
        return {"ok": False, "image_model": wanted, "note": "self-test: not checked"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get("https://generativelanguage.googleapis.com/v1beta/models",
                                params={"pageSize": 1000}, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    if resp.status_code != 200:
        return {"ok": False, "status": resp.status_code, "detail": resp.text[:300]}
    names = [m["name"].split("/", 1)[1] for m in resp.json().get("models", [])]
    images = sorted(n for n in names if "image" in n)
    return {"ok": wanted in names, "image_model": wanted, "image_models_listed": images}


def owner_headers() -> dict[str, str]:
    from platform_testing.db_helpers import ensure_auth_user

    user_id = uuid.uuid4()

    async def seed() -> None:
        engine = create_async_engine(DB, poolclass=NullPool)
        async with AsyncSession(engine) as session:
            await ensure_auth_user(session, user_id, f"gemini-{user_id.hex[:8]}@locah.test")
            await session.commit()
        await engine.dispose()

    asyncio.run(seed())
    token = jwt.encode({"sub": str(user_id), "email": f"gemini-{user_id.hex[:8]}@locah.test",
                        "exp": datetime.now(timezone.utc) + timedelta(hours=3)},
                       os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def run_job(job_id: str) -> None:
    from platform_core.services.website_generation import WebsiteGenerationService

    async def go() -> None:
        engine = create_async_engine(DB, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                await WebsiteGenerationService.execute_job(
                    session, generation_job_id=uuid.UUID(job_id), correlation_id=str(uuid.uuid4()))
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(go())


class Owner:
    def __init__(self, client: TestClient, headers: dict[str, str], business_id: str) -> None:
        self.client, self.id = client, business_id
        self.headers = {**headers, "X-Business-Id": business_id, "X-Operating-Context": "business"}
        self.revision = self.interview()["blueprint"]["revision"]

    def interview(self) -> dict[str, Any]:
        data: dict[str, Any] = self.client.get(f"/v1/b/{self.id}/interview", headers=self.headers).json()["data"]
        return data

    def send(self, action: str, **body: Any) -> dict[str, Any]:
        self.revision = self.interview()["blueprint"]["revision"]
        res = self.client.post(f"/v1/b/{self.id}/interview", headers=self.headers, json={
            "revision": self.revision, "request_id": str(uuid.uuid4()), "action": action, **body})
        if res.status_code != 200:
            raise RuntimeError(f"{action}: {res.status_code} {res.text[:300]}")
        data: dict[str, Any] = res.json()["data"]
        return data

    def site(self) -> dict[str, Any]:
        data: dict[str, Any] = self.client.get(f"/v1/b/{self.id}/website", headers=self.headers).json()["data"]
        return data

    def hero(self) -> dict[str, Any]:
        home = next(p for p in self.site()["draft"]["pages"] if p["slug"] == "home")
        return next(s for s in home["sections"] if s["section_type_id"] == "hero")

    def post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        res = self.client.post(f"/v1/b/{self.id}{path}", headers=self.headers, json=body or {})
        return {"status": res.status_code, **(res.json() if res.content else {})}

    def patch_section(self, section: dict[str, Any], content: dict[str, Any]) -> int:
        res = self.client.patch(f"/v1/b/{self.id}/website/sections/{section['id']}", headers=self.headers,
                                json={"content": content})
        return int(res.status_code)


def personas() -> list[dict[str, Any]]:
    from platform_testing.interview_personas import ALL_PERSONAS

    chosen = [{"key": p.key, "name": p.name, "category": p.category[:2], "opening": p.opening[0],
               "answers": {ask: text for ask, (text, _) in p.answers.items()}}
              for p in ALL_PERSONAS if p.key in GOLDEN]
    return sorted(chosen, key=lambda c: GOLDEN.index(c["key"]))


def converse(owner: Owner, spec: dict[str, Any]) -> list[dict[str, str]]:
    """The owner's own words, answering whatever LOCAH (real Gemini) asks.
    Photos: the owner has none ("Not sure" / no photos answer is never an upload)."""
    said: list[dict[str, str]] = []
    data = owner.send("turn", text=spec["opening"])
    said.append({"owner": spec["opening"]})
    for _ in range(9):
        bp = data["blueprint"]
        said.append({"locah": bp["messages"][-1]["text"]})
        if bp.get("checkpoint_turn") is not None and bp["completion_state"].get("ready_at"):
            break
        ask = (bp.get("asks") or [{}])[-1].get("ask", "")
        text = spec["name"] if ask == "name" else ("I don't have photos." if ask == "photos"
                                                     else spec["answers"].get(ask, NOT_SURE))
        data = owner.send("turn", text=text)
        said.append({"owner": text})
    return said


def owner_photo(business_id: str) -> str:
    """An owner's own photo, uploaded (a real JPEG file; not Gemini's)."""
    from PIL import Image, ImageDraw

    asset = str(uuid.uuid4())
    key = f"uploads/{business_id}/{asset}.jpg"
    img = Image.new("RGB", (1600, 1000), (120, 96, 70))
    ImageDraw.Draw(img).text((40, 40), "OWNER'S OWN PHOTO", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    (MEDIA / key).parent.mkdir(parents=True, exist_ok=True)
    (MEDIA / key).write_bytes(buf.getvalue())
    url = f"{MEDIA_URL}/{key}"
    sql("insert into media_assets (id, business_id, mime_type, bucket, storage_key, purpose, status, public_url, "
        "size_bytes) values (:id, :b, 'image/jpeg', 'media', :k, 'website', 'ready', :u, :n)",
        id=asset, b=business_id, k=key, u=url, n=len(buf.getvalue()))
    return asset


# ------------------------------------------------------------------ checks

def verify_hero(owner: Owner, job_id: str, slug: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    hero = owner.hero()
    asset_id = hero["content"].get("image_asset_id")
    checks["hero_has_picture"] = bool(asset_id)
    if not asset_id:
        return checks
    row = sql("select source_type, approval_state, generated_for, generation_job_id, prompt_version, mime_type, "
              "size_bytes, public_url from media_assets where id = :a", a=asset_id)
    checks["persisted_media_asset"] = bool(row)
    if row:
        source, approval, slot, gen_job, version, mime, size, url = row[0]
        checks["marked_gemini_generated_draft"] = (source, approval) == ("gemini_generated", "draft")
        checks["provenance_slot_job_prompt"] = (slot == "hero" and str(gen_job) == job_id
                                                and str(version).startswith("media-v4"))
        checks["returned_by_gemini"] = not SELF_TEST and source == "gemini_generated" and str(mime).startswith(
            "image/") and (
            (MEDIA / url.split(MEDIA_URL + "/", 1)[-1]).stat().st_size > 10_000 if LOCAL_STORAGE else True)
    plan = {p["key"]: p for p in owner.interview()["blueprint"]["media_plan"]}
    checks["media_plan_hero_slot"] = (plan.get("hero", {}).get("asset_id") == asset_id
                                      and plan["hero"]["status"] == "ready")
    checks["rendered_in_preview"] = bool(hero.get("assets", {}).get("image_asset_id", {}).get("url"))
    public = owner.client.get(f"/v1/public/websites/{slug}")
    body = json.dumps(public.json()) if public.status_code == 200 else ""
    checks["rendered_after_publish"] = asset_id in body or (row and row[0][7] and row[0][7] in body)
    # The editor's own controls, on the published site's draft.
    checks["approvable"] = owner.post(f"/media/{asset_id}/approve")["status"] == 200 and sql(
        "select approval_state from media_assets where id = :a", a=asset_id)[0][0] == "approved"
    mine = owner_photo(owner.id)
    checks["replaceable"] = owner.patch_section(hero, {**hero["content"], "image_asset_id": mine}) == 200 \
        and owner.hero()["content"]["image_asset_id"] == mine
    now = owner.hero()
    checks["removable"] = owner.patch_section(now, {k: v for k, v in now["content"].items()
                                                    if k != "image_asset_id"}) == 200 \
        and not owner.hero()["content"].get("image_asset_id")
    return checks


def manual_controls(owner: Owner) -> dict[str, Any]:
    """Website editor → Hero → Generate / Generate a new picture / Keep / Remove / Upload; one card."""
    out: dict[str, Any] = {}
    hero = owner.hero()
    first = owner.post(f"/website/sections/{hero['id']}/generate-image")
    out["generate"] = bool(first.get("data", {}).get("ok"))
    second = owner.post(f"/website/sections/{hero['id']}/generate-image")
    out["generate_new"] = bool(second.get("data", {}).get("ok")) and \
        second["data"]["asset"]["id"] != first.get("data", {}).get("asset", {}).get("id")
    current = owner.hero()["content"].get("image_asset_id")
    out["shows_new_picture"] = current == second.get("data", {}).get("asset", {}).get("id")
    out["keep"] = owner.post(f"/media/{current}/approve")["status"] == 200
    hero = owner.hero()
    out["remove"] = owner.patch_section(hero, {k: v for k, v in hero["content"].items() if k != "image_asset_id"}) \
        == 200 and not owner.hero()["content"].get("image_asset_id")
    mine = owner_photo(owner.id)
    hero = owner.hero()
    out["upload_my_photo"] = owner.patch_section(hero, {**hero["content"], "image_asset_id": mine}) == 200 \
        and owner.hero()["content"]["image_asset_id"] == mine
    home = next(p for p in owner.site()["draft"]["pages"] if p["slug"] == "home")
    cards = next((s for s in home["sections"] if (s.get("image_policy") or {}).get("items") == "draw"
                  and s["content"].get("items")), None)
    if cards:
        card = owner.post(f"/website/sections/{cards['id']}/generate-image", {"list_key": "items", "index": 0})
        out["card_generate"] = bool(card.get("data", {}).get("ok"))
    return out


async def read_menu_pdf() -> dict[str, Any]:
    """Real Gemini document extraction on a menu PDF; nothing may be invented."""
    from PIL import Image, ImageDraw

    from platform_core.interview import documents

    page = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(page)
    y = 80
    draw.text((80, y), "NALLA VEEDU KITCHEN — MENU", fill="black")
    printed = ""
    for group, printed_rows in MENU:
        y += 70
        draw.text((80, y), group.upper(), fill="black")
        for name, price in printed_rows:
            y += 45
            draw.text((110, y), f"{name}  ....  Rs {price}", fill="black")
            printed += f"{name} {price} "
    buf = io.BytesIO()
    page.save(buf, "PDF", resolution=150)
    (OUT / "menu.pdf").write_bytes(buf.getvalue())
    if SELF_TEST:
        return {"ok": False, "note": "self-test: not read"}
    read_kind, groups, facts = await documents.read(buf.getvalue(), "application/pdf")
    items: list[tuple[str, str, str]] = [(g.name, i.name, i.price) for g in groups for i in g.items]
    invented = [i for i in items if i[2] and i[2].replace(",", "") not in printed]
    expected = {name for _, rows in MENU for name, _ in rows}
    found = {i[1] for i in items}
    return {"ok": bool(items) and not invented, "kind": read_kind, "items": items, "invented_prices": invented,
            "missed": sorted(expected - found), "facts": facts}


# -------------------------------------------------------------------- main

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    calls: dict[str, int] = {}
    if LOCAL_STORAGE:
        local_storage(calls)
    sys.path.insert(0, str(Path(__file__).parent))
    count_gemini_images(calls)
    from platform_api.main import app

    report: dict[str, Any] = {"mode": "SELF-TEST (stand-in pixels, nothing verified)" if SELF_TEST else "REAL GEMINI",
                              "storage": ("local file (self-test plates)" if SELF_TEST else
                                          "local file (Gemini bytes)" if LOCAL_STORAGE else "Supabase Storage"),
                              "model_check": asyncio.run(check_model()), "sites": []}
    headers = owner_headers()
    results = []
    with TestClient(app) as client:
        for spec in personas():
            cat, sub = spec["category"]
            before = calls.get("gemini_images", 0)
            business_id = client.post("/v1/platform/businesses/start", headers=headers, json={
                "category_key": cat, "subcategory_key": sub}).json()["data"]["business"]["id"]
            owner = Owner(client, headers, business_id)
            transcript = converse(owner, spec)
            if owner.interview()["blueprint"].get("name_pending"):
                owner.send("correct", slot="name", values=[], text=spec["name"])
            job_id = owner.send("build")["blueprint"]["completion_state"]["generation_job_id"]
            run_job(job_id)
            status, usage = sql("select status, provider_usage from website_generation_jobs where id = :j", j=job_id)[0]
            published = owner.post("/website/publish")
            slug = sql("select slug from businesses where id = :b", b=business_id)[0][0]
            theme = owner.site()["draft"]["theme"]
            checks = verify_hero(owner, job_id, slug) if published["status"] == 200 else {"published": False}
            # Re-publish with the Gemini hero back on, for the screenshots.
            owner.post("/website/publish")
            site = {"key": spec["key"], "name": spec["name"], "business_id": business_id, "slug": slug,
                    "job": status, "creative_source": usage.get("creative_strategy"),
                    "fallback_reason": usage.get("fallback_reason"), "media_drawn": usage.get("media_drawn"),
                    "gemini_images_this_site": calls.get("gemini_images", 0) - before,
                    "visual_consent": owner.interview()["blueprint"]["visual_consent"],
                    "hero_style": theme.get("hero_style"), "palette": theme.get("palette_key"),
                    "checks": checks, "transcript": transcript}
            report["sites"].append(site)
            results.append({k: site[k] for k in ("key", "name", "business_id", "slug", "hero_style", "palette")})
            print(f"{spec['key']}: /{slug} drawn={usage.get('media_drawn')} checks="
                  f"{sum(bool(v) for v in checks.values())}/{len(checks)}")
        first = Owner(client, headers, report["sites"][0]["business_id"])
        report["manual_controls"] = manual_controls(first)
        # The owner's own uploaded hero wins.
        spec = personas()[0]
        business_id = client.post("/v1/platform/businesses/start", headers=headers, json={
            "category_key": spec["category"][0], "subcategory_key": spec["category"][1]}).json()["data"]["business"]["id"]
        owner = Owner(client, headers, business_id)
        converse(owner, spec)
        mine = owner_photo(business_id)
        owner.send("media", media={"asset_id": mine, "role": "hero", "label": "Our kitchen", "source": "USER_UPLOAD"})
        job_id = owner.send("build")["blueprint"]["completion_state"]["generation_job_id"]
        run_job(job_id)
        report["upload_wins"] = owner.hero()["content"].get("image_asset_id") == mine
    report["menu_pdf"] = asyncio.run(read_menu_pdf())
    report["gemini_images_total"] = calls.get("gemini_images", 0)
    report["image_models_seen"] = sorted(MODELS)

    heroes = [s["checks"] for s in report["sites"]]
    real = not SELF_TEST and report["model_check"].get("ok") and "SELF-TEST" not in MODELS
    report["REAL_GEMINI_IMAGES_VERIFIED"] = "YES" if real and heroes and all(all(c.values()) for c in heroes) else "NO"
    report["MANUAL_IMAGE_GENERATION_VERIFIED"] = "YES" if real and all(report["manual_controls"].values()) else "NO"
    report["NO_IMAGE_OWNER_FLOW_VERIFIED"] = "YES" if real and all(
        (s["media_drawn"] or 0) > 0 and s["checks"].get("hero_has_picture") for s in report["sites"]) else "NO"
    report["UPLOAD_WINS"] = "YES" if report["upload_wins"] else "NO"
    report["MENU_PDF_REAL_GEMINI"] = "YES" if real and report["menu_pdf"].get("ok") else "NO"
    (OUT / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    for key in ("REAL_GEMINI_IMAGES_VERIFIED", "MANUAL_IMAGE_GENERATION_VERIFIED", "NO_IMAGE_OWNER_FLOW_VERIFIED",
                "UPLOAD_WINS", "MENU_PDF_REAL_GEMINI"):
        print(f"{key} = {report[key]}")
    print(f"report: {OUT / 'report.json'}")


if __name__ == "__main__":
    main()
