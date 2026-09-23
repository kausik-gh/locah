"""Which pictures a website needs, and drawing the ones the owner agreed to.

A gradient hero over text cards is the look of a site with no pictures, and
most small businesses start with none. This decides, per site, the few images
that change it most — one hero, and a picture per category (or per dish, or per
project) — and draws them only when the owner said yes to draft visuals.

Rules:

* The owner's own photos always win; a slot with a real photo is never drawn.
* Draft visuals are marked AI_GENERATED and labelled as drafts; they are
  illustrative, never presented as a photograph of this shop or its stock.
* Each slot is drawn once and cached by key; a rebuild reuses it.
* Only what improves the composition: a hero and up to six more, never a wall
  of random images. The budget depends on the archetype.
* The prompt carries the trade and the owner's own item names — never the
  transcript, never people, text, logos or prices.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from platform_core.interview.creative_director import CreativeDirection
from platform_core.interview.models import BusinessBlueprint, MediaGenerationRequest, MediaReference
from platform_core.website.image_generation import GeneratedImage, generate_image

# Most images per site besides the hero, by archetype.
BUDGET: dict[str, int] = {
    "product_commerce": 5, "menu_commerce": 6, "membership_fitness": 0,
    "real_estate_projects": 3, "service_appointment": 3, "b2b_rfq": 3,
    "project_portfolio": 3, "local_service": 3,
}

_NEVER = (
    "No text, words, letters, numbers, logos, labels, packaging, price tags, signage or "
    "watermarks. No people, faces or hands."
)


@dataclass(frozen=True)
class Slot:
    key: str  # "hero", "category:chicken", "item:seer-fish", "project:green-meadows"
    subject: str
    aspect: str
    role: str  # MediaReference role it becomes
    label: str


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:60]


def _clean(text: str) -> str:
    # Owner words only, and nothing that reads as a number or a claim.
    return re.sub(r"\s+", " ", re.sub(r"[\d₹$]+", "", text)).strip(" ,.-")[:80]


def plan_slots(bp: BusinessBlueprint, direction: CreativeDirection) -> list[Slot]:
    """The pictures this site should have, most important first."""
    groups = bp.taxonomy.groups
    names = [_clean(g.name) for g in groups if _clean(g.name)]
    hero_subject = (
        ", ".join(names[:4]) if names and direction.archetype in {
            "product_commerce", "menu_commerce"} else ""
    )
    slots = [Slot("hero", hero_subject, "16:9" if direction.hero in {
        "cinematic", "editorial_overlay"} else "4:3", "hero", "Draft visual · cover")]
    budget = BUDGET.get(direction.archetype, 3)
    if direction.archetype in {"menu_commerce", "real_estate_projects"}:
        # Dishes and projects are what visitors choose between: picture them.
        kind = "item" if direction.archetype == "menu_commerce" else "project"
        picked = 0
        for depth in range(3):
            for group in groups:
                if depth < len(group.items) and picked < budget:
                    item = group.items[depth]
                    subject = _clean(f"{item.name} ({group.name})") if kind == "item" else _clean(item.name)
                    slots.append(Slot(f"{kind}:{slug(item.name)}", subject, "4:3", "offering",
                                      f"Draft visual · {item.name}"[:120]))
                    picked += 1
        if picked:
            return slots
    for group in groups[:budget]:
        members = ", ".join(_clean(i.name) for i in group.items[:4] if _clean(i.name))
        subject = _clean(group.name) + (f" — {members}" if members else "")
        slots.append(Slot(f"category:{slug(group.name)}", subject, "4:3", "offering",
                          f"Draft visual · {group.name}"[:120]))
    return slots


def prompt_for(slot: Slot, direction: CreativeDirection, trade: str) -> str:
    framing = {
        "cinematic": "Wide composition with calm, darker space on the left for a headline.",
        "editorial_overlay": "Wide composition with calm space on the left for a headline.",
        "commerce_split": "The subject fills the frame, centred, photographed close.",
        "airy_split": "Architecture on the right, open bright sky on the left.",
        "editorial_split": "The subject fills the frame, softly lit.",
    }[direction.hero] if slot.key == "hero" else "The subject fills the frame, centred."
    subject = slot.subject or trade
    return (
        f"A realistic, professional draft photograph for a small business website ({trade}). "
        f"Subject: {subject}. Style: {direction.image_style}. {framing} {_NEVER}"
    )


def cached(bp: BusinessBlueprint, key: str) -> UUID | None:
    """A picture for this slot: the owner's first, then a drawn draft."""
    request = next((r for r in bp.media_generation_requests
                    if r.role == "visual" and r.key == key and r.status == "ready" and r.asset_id), None)
    return request.asset_id if request else None


def owner_photo(bp: BusinessBlueprint, slot: Slot) -> UUID | None:
    uploads = [m for m in bp.media_assets if m.source == "USER_UPLOAD" and m.role != "logo"]
    if slot.key == "hero":
        hero = next((m for m in uploads if m.role == "hero"), None)
        return hero.asset_id if hero else None
    name = slot.key.split(":", 1)[1]
    for media in uploads:
        if media.role in {"offering", "gallery", "business"} and slug(media.label).startswith(name[:12]):
            return UUID(str(media.asset_id))
    return None


def picture_for(bp: BusinessBlueprint, key: str) -> str | None:
    """The asset id to show in a slot, if there is one."""
    for media in bp.media_assets:
        if media.source == "USER_UPLOAD" and media.role == "hero" and key == "hero":
            return str(media.asset_id)
    found = cached(bp, key)
    if found:
        return str(found)
    if key == "hero":
        hero = next((m for m in bp.media_assets if m.role == "hero"), None)
        return str(hero.asset_id) if hero else None
    name = key.split(":", 1)[1] if ":" in key else key
    for media in bp.media_assets:
        if media.source == "USER_UPLOAD" and media.role in {"offering", "gallery", "business"} and (
            slug(media.label).startswith(name[:12])
        ):
            return str(media.asset_id)
    return None


Drawer = Callable[[str, str], Awaitable[tuple[GeneratedImage | None, str]]]


async def draw_missing(
    bp: BusinessBlueprint,
    direction: CreativeDirection,
    trade: str,
    *,
    draw: Drawer | None = None,
    concurrency: int = 3,
) -> list[tuple[Slot, GeneratedImage | None, str]]:
    """Draw the slots that have no picture yet, a few at a time. Consent first."""
    if bp.visual_consent != "draft_visuals":
        return []
    todo = [s for s in plan_slots(bp, direction)
            if not owner_photo(bp, s) and not cached(bp, s.key)]
    if not todo:
        return []
    gate = asyncio.Semaphore(concurrency)
    drawer = draw or (lambda prompt, aspect: generate_image(prompt, aspect_ratio=aspect, timeout_seconds=75))

    async def one(slot: Slot) -> tuple[Slot, GeneratedImage | None, str]:
        async with gate:
            image, reason = await drawer(prompt_for(slot, direction, trade), slot.aspect)
            return slot, image, reason

    return list(await asyncio.gather(*(one(s) for s in todo)))


def record(bp: BusinessBlueprint, slot: Slot, asset_id: UUID | None, reason: str = "") -> None:
    """Remember a drawn (or failed) slot on the Blueprint."""
    bp.media_generation_requests = [
        r for r in bp.media_generation_requests if not (r.role == "visual" and r.key == slot.key)
    ]
    bp.media_generation_requests.append(MediaGenerationRequest(
        role="visual", key=slot.key, status="ready" if asset_id else "failed",
        asset_id=asset_id, reason=None if asset_id else (reason or "error"),
    ))
    if asset_id and all(m.asset_id != asset_id for m in bp.media_assets):
        bp.media_assets.append(MediaReference(
            asset_id=asset_id, role=slot.role if slot.role in {"hero", "offering"} else "gallery",
            label=slot.label, source="AI_GENERATED",
        ))
