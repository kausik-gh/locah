"""Website creative v4 — the real owner flow, run locally for five businesses.

    tools/acceptance/stack/db.sh locah_accept
    uv run python tools/acceptance/stack/owner_flow_v4.py acceptance-out/v4
    # then the API (api.sh), the web app (web.sh) and a file server for the
    # stand-in pictures:  python -m http.server 8899 -d acceptance-out/v4/media
    node tools/acceptance/owner_sites.mjs acceptance-out/v4

Every step is the product's own: Create Business → talk to LOCAH (typed
messages, through the interview API) → Build → the real `website.generate`
worker job (MediaPlan, CreativeDirector, composition, draft merge) → Publish.

Test-only stand-ins, behind the kill switch (LOCAH_TEST_NO_EXTERNAL_AI=1,
no provider keys):

* the conversation and the creative plan take the model-down path (no model
  is called; the deterministic reading and direction are what ship when
  Gemini is unreachable);
* Gemini's image BYTES are replaced by a labelled placeholder plate (a
  gradient with the slot's subject written on it) and the storage upload by
  a local file. Where each picture goes, its prompt, its provenance and the
  whole design are the real ones — only the pixels are stand-ins.

Local databases only. Never point this at staging.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB = os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@localhost:54329/locah_accept")
if "@localhost:" not in DB and "@127.0.0.1:" not in DB:
    sys.exit("local databases only")
os.environ["API_DATABASE_URL"] = DB
os.environ["LOCAH_TEST_NO_EXTERNAL_AI"] = "1"
os.environ["SUPABASE_JWT_SECRET"] = "local-acceptance-secret-with-at-least-32-characters"
os.environ["WEBSITE_PREVIEW_SECRET"] = "local-preview-secret-with-at-least-32-characters"
os.environ["RATE_LIMIT_ENABLED"] = "0"
os.environ["LOCAH_JOBS_INERT"] = "1"
for key in ("GEMINI_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AI_PROVIDER",
            "SUPABASE_URL", "SUPABASE_JWKS_URL"):
    os.environ.pop(key, None)

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
MODEL_DOWN = "--model-down" in sys.argv
OUT = Path(ARGS[0] if ARGS else "acceptance-out/v4").resolve()
MEDIA = OUT / "media"
MEDIA_URL = os.getenv("LOCAH_V4_MEDIA_URL", "http://localhost:8899")

NOT_SURE = "Not sure about that — you decide."
GOLDEN = ("home-food", "gym", "real-estate", "meat-shop", "industrial")

# --model-down: five owners in free text with NO model reading at all — what
# ships when Gemini is unreachable. Five owners, in their own words. Nothing below is a template: each is only
# what that owner would type.
OWNERS: list[dict[str, Any]] = [
    {
        "key": "home-food", "category": ("home_food", "home_kitchen"), "name": "Nalla Veedu Kitchen",
        "say": [
            "Nalla Veedu Kitchen is my home kitchen in Velachery, Chennai. I cook Chettinad and "
            "Tamil home-style food — idli, dosa batter, meals, kuzhambu, and podi and pickles in jars.",
            "People order on WhatsApp a day before, and we deliver around Velachery and Taramani or "
            "they pick up from home.",
            "Idli podi is 120 for 200 g, dosa batter is 80 per litre, lunch meals 150.",
            "My WhatsApp is 9840123456. We cook from 7 am to 2 pm, Monday to Saturday.",
            "I don't have photos yet — please create draft pictures.",
        ],
    },
    {
        "key": "gym", "category": ("fitness", "powerlifting"), "name": "Grit Barbell Club",
        "say": [
            "Grit Barbell Club is a strength gym in Anna Nagar, Chennai. Powerlifting, barbell "
            "training and coached small-group strength classes. Raw, serious, no mirrors-and-selfies vibe.",
            "Monthly membership is 3500, quarterly 9500. First session is a free trial — people book "
            "a trial on WhatsApp.",
            "Open 5:30 am to 10 pm every day. WhatsApp 9003012345.",
            "No photos right now, you can make some.",
        ],
    },
    {
        "key": "real-estate", "category": ("real_estate", "developer"), "name": "Aranya Homes",
        "say": [
            "Aranya Homes is a residential developer in Coimbatore. We build calm, green villa "
            "communities and apartments near Saravanampatti and Thudiyalur.",
            "Our projects: Aranya Meadows, 3 and 4 BHK villas; Aranya Heights, 2 and 3 BHK apartments.",
            "Buyers book a site visit or call us. Office on Sathy Road, Coimbatore. Phone 9894012345.",
            "We will share real project photos later; for now make drafts.",
        ],
    },
    {
        "key": "meat-shop", "category": ("fresh_grocery", "meat_shop"), "name": "Ishant Proteins",
        "say": [
            "Ishant Proteins is a fresh meat shop. We sell chicken, mutton and fish by the kg, cut "
            "fresh to order, and people order on WhatsApp.",
            "We deliver around Nookampalayam and Perumbakkam, people can also pick up from the shop.",
            "Nookampalayam Road, Chennai. WhatsApp 8754722026.",
            "No photos, please create them.",
        ],
        "catalogue": [{"group": "Chicken", "price": "240", "unit": "per kg"},
                      {"group": "Mutton", "price": "850", "unit": "per kg"}],
    },
    {
        "key": "industrial", "category": ("industrial", "industrial_supplier"), "name": "Sakthi Pumps & Valves",
        "say": [
            "Sakthi Pumps & Valves supplies industrial pumps, valves and motors to factories, textile "
            "mills and contractors across Tamil Nadu. We are in Peelamedu, Coimbatore.",
            "Monoblock pumps, submersible pumps, gate valves and ball valves, three-phase motors.",
            "Customers ask for a quote by phone or WhatsApp. Phone 9842212345. Monday to Saturday, 9 to 7.",
            "No photos yet, drafts are fine.",
        ],
    },
]


def _font(size: int) -> Any:
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def plate(prompt: str, aspect: str) -> bytes:
    """A labelled stand-in for Gemini's picture: the slot's subject on a lit gradient. Not a photo."""
    w, h = {"16:9": (1600, 900), "4:3": (1200, 900), "3:4": (900, 1200), "1:1": (1000, 1000),
            "4:5": (960, 1200), "3:2": (1500, 1000), "21:9": (2100, 900)}.get(aspect, (1400, 1000))
    seed = hashlib.sha256(prompt.encode()).digest()
    dark = bool(re.search(r"low-key|dark|night|moody|dramatic", prompt, re.I))
    warm = bool(re.search(r"warm|golden|terracotta|brass|kitchen|spice|amber", prompt, re.I))
    base = (38, 30, 26) if dark else (238, 230, 218)
    tint = (196, 120, 60) if warm else (90, 120, 140)
    img = Image.new("RGB", (w, h), base)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(base[i] * (1 - t * 0.5) + tint[i] * t * 0.5) for i in range(3)))
    glow = Image.new("L", (w, h), 0)
    gx, gy = int(w * (0.3 + seed[0] / 600)), int(h * (0.35 + seed[1] / 800))
    ImageDraw.Draw(glow).ellipse([gx - w // 3, gy - h // 3, gx + w // 3, gy + h // 3], fill=150)
    img = Image.composite(Image.new("RGB", (w, h), tint), img, glow.filter(ImageFilter.GaussianBlur(w // 8)))
    subject = re.search(r"(?:Subject|Motif):\s*([^.;]{2,80})", prompt)
    label = (subject.group(1) if subject else prompt[:60]).strip()
    draw = ImageDraw.Draw(img)
    # A small tag, bottom-right: enough to never mistake it for a photo, out of the way of the design.
    tag = f"STAND-IN · {label[:48]}"
    x0, y0 = w - 24 - 11 * len(tag), h - 58
    draw.rectangle([x0, y0, w - 24, h - 24], fill=(0, 0, 0) if not dark else (255, 255, 255))
    draw.text((x0 + 10, y0 + 6), tag, font=_font(18), fill=(255, 255, 255) if not dark else (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def stubs() -> list[str]:
    """Gemini's image bytes and the storage upload only. Returns the prompts seen."""
    import platform_core.interview.media_director as md
    import platform_core.media.supabase_storage as storage
    import platform_core.website.image_generation as images
    from platform_core.website.image_generation import GeneratedImage

    seen: list[str] = []
    images.image_generation_available = lambda: True

    async def draw(prompt: str, *, aspect_ratio: str = "16:9", timeout_seconds: int = 60) -> Any:
        seen.append(prompt)
        return GeneratedImage(mime_type="image/jpeg", bytes=plate(prompt, aspect_ratio), model="stand-in",
                              latency_ms=1, prompt=prompt), ""

    async def put(*, storage_key: str, body: bytes, **_: Any) -> None:
        path = MEDIA / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    md.generate_image = draw
    storage.put_generated_object = put
    storage.public_url = lambda bucket, key: f"{MEDIA_URL}/{key}"
    return seen


def owner_headers() -> dict[str, str]:
    from platform_testing.db_helpers import ensure_auth_user

    user_id = uuid.uuid4()

    async def seed() -> None:
        engine = create_async_engine(DB, poolclass=NullPool)
        async with AsyncSession(engine) as session:
            await ensure_auth_user(session, user_id, f"v4-{user_id.hex[:8]}@locah.test")
            await session.commit()
        await engine.dispose()

    asyncio.run(seed())
    token = jwt.encode({"sub": str(user_id), "email": f"v4-{user_id.hex[:8]}@locah.test",
                        "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
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
        self.revision = self.get()["blueprint"]["revision"]
        self.transcript: list[dict[str, str]] = []

    def get(self) -> dict[str, Any]:
        data: dict[str, Any] = self.client.get(f"/v1/b/{self.id}/interview", headers=self.headers).json()["data"]
        return data

    def send(self, action: str, **body: Any) -> dict[str, Any]:
        res = self.client.post(f"/v1/b/{self.id}/interview", headers=self.headers, json={
            "revision": self.revision, "request_id": str(uuid.uuid4()), "action": action, **body})
        if res.status_code != 200:
            raise RuntimeError(f"{action}: {res.status_code} {res.text[:400]}")
        data: dict[str, Any] = res.json()["data"]
        self.revision = data["blueprint"]["revision"]
        return data

    def say(self, text: str) -> dict[str, Any]:
        data = self.send("turn", text=text)
        reply = next((m["text"] for m in reversed(data["blueprint"]["messages"]) if m["role"] == "assistant"), "")
        self.transcript += [{"owner": text}, {"locah": reply}]
        return data


def personas() -> list[dict[str, Any]]:
    """The acceptance personas for the five golden kinds, with their scripted
    model readings written where the replay provider serves them."""
    from platform_testing.interview_personas import ALL_PERSONAS

    recordings: dict[str, Any] = {}
    chosen = []
    for p in ALL_PERSONAS:
        recordings[p.opening[0]] = p.opening[1]
        recordings.update({text: data for text, data in p.answers.values()})
        if p.key in GOLDEN:
            chosen.append({"key": p.key, "name": p.name, "category": p.category[:2], "opening": p.opening[0],
                           "answers": {ask: text for ask, (text, _) in p.answers.items()}})
    path = OUT / "replay_ai.json"
    path.write_text(json.dumps(recordings, ensure_ascii=False), encoding="utf-8")
    os.environ["AI_PROVIDER"] = "replay"
    os.environ["LOCAH_AI_REPLAY_FILE"] = str(path)
    return sorted(chosen, key=lambda c: GOLDEN.index(c["key"]))


def converse(owner: "Owner", spec: dict[str, Any]) -> None:
    """Answer whatever LOCAH asks, as the persona would (flows.mjs's loop)."""
    data = owner.say(spec["opening"])
    for _ in range(9):
        bp = data["blueprint"]
        if bp.get("checkpoint_turn") is not None and bp["completion_state"].get("ready_at"):
            break
        ask = (bp.get("asks") or [{}])[-1].get("ask", "")
        data = owner.say(spec["name"] if ask == "name" else spec["answers"].get(ask, NOT_SURE))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    owners = OWNERS if MODEL_DOWN else personas()
    from platform_api.main import app

    prompts = stubs()
    headers = owner_headers()
    results = []
    with TestClient(app) as client:
        for spec in owners:
            before = len(prompts)
            cat, sub = spec["category"]
            started = client.post("/v1/platform/businesses/start", headers=headers, json={
                "category_key": cat, "subcategory_key": sub})
            if started.status_code != 200:
                raise RuntimeError(started.text)
            business_id = started.json()["data"]["business"]["id"]
            owner = Owner(client, headers, business_id)
            if MODEL_DOWN:
                for line in spec["say"]:
                    owner.say(line)
            else:
                converse(owner, spec)
            if owner.get()["blueprint"].get("name_pending"):
                owner.send("correct", slot="name", values=[], text=spec["name"])
            if spec.get("catalogue"):
                owner.send("catalogue", catalogue=spec["catalogue"])
            data = owner.send("build")
            bp = data["blueprint"]
            job_id = bp["completion_state"]["generation_job_id"]
            run_job(job_id)
            site = client.get(f"/v1/b/{business_id}/website", headers=owner.headers).json()["data"]
            published = client.post(f"/v1/b/{business_id}/website/publish", headers=owner.headers)
            if published.status_code != 200:
                raise RuntimeError(f"publish: {published.text[:400]}")
            from platform_testing.phase_b import sql

            slug = sql("select slug from businesses where id = :b", b=business_id)[0][0]

            usage = sql("select status, provider_usage from website_generation_jobs where id = :j", j=job_id)[0]
            theme = site["draft"]["theme"]
            results.append({
                "key": spec["key"], "name": spec["name"], "business_id": business_id, "slug": slug,
                "visual_consent": owner.get()["blueprint"]["visual_consent"],
                "job": {"status": usage[0], "usage": usage[1]},
                "hero_style": theme.get("hero_style"), "family": theme.get("family"),
                "palette": theme.get("palette_key"), "type_system": theme.get("type_system"),
                "sections": [f"{s['section_type_id']}:{s.get('layout_variant')}"
                             for s in site["draft"]["pages"][0]["sections"]],
                "pictures_drawn": len(prompts) - before,
                "transcript": owner.transcript,
            })
            print(f"{spec['key']}: /{slug}  hero={theme.get('hero_style')}  pictures={len(prompts) - before}  "
                  f"job={usage[0]}")
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    (OUT / "prompts.json").write_text(json.dumps(prompts, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
