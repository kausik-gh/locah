"""The one place LOCAH writes image prompts for a website.

Before this, two systems disagreed: the MediaDirector asked for realistic
draft photographs in the site's own style, while the older helpers asked for
"abstract artwork that must not read as a photograph" keyed only on a
business type. A site could get one of each. Now every picture for a site —
drawn by the build, by the owner's request in the interview, or from the
editor's "Generate a picture" — is written here, from the same *shoot brief*,
so all of a site's pictures look like one shoot for one brand.

What a prompt may show follows the media truth policy
(`interview.models.TruthClass`):

* mood / representative → an editorial photograph (a kind of dish, a kind of
  room, the trade's atmosphere) — never captioned or presented as theirs;
* graphic → texture or illustration, where realism would mislead;
* factual → never drawn: only the owner's own asset can fill it.

Prompts never carry the transcript, prices, numbers, people, text or logos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PROMPT_VERSION = "media-v4.1"

_NEVER = (
    "One continuous photograph of a single scene — no collage, split panels, borders, frames or inset "
    "pictures. No text, words, letters, numbers, logos, labels, packaging, price tags, signage or "
    "watermarks. No people, faces or hands."
)
_NEVER_GRAPHIC = (
    "No text, letters, numbers, logos or signage. No people or faces. Not a photograph of a real place "
    "or product."
)


@dataclass(frozen=True)
class ShootBrief:
    """What every picture of one website shares: one light, one lens, one world."""

    world: str  # the trade's material world ("rustic clay and brass on banana leaf, …")
    light: str
    lens: str
    grade: str
    palette: tuple[str, ...] = ()

    def sentence(self) -> str:
        colours = ", ".join(c for c in self.palette if c)
        accents = f" Colour accents that sit with {colours}." if colours else ""
        return (f"Part of one editorial series for this brand: {self.world}. Light: {self.light}. "
                f"Lens: {self.lens}. Colour grade: {self.grade}.{accents}")


# Light and grade follow the site's ground: a dark site is shot low-key, a light
# one airy. The world itself comes from the direction's image style.
_LOW_KEY = ("low-key directional side light with deep shadows", "rich, deep, slightly desaturated")
_AIRY = ("soft natural daylight from a window, gentle shadows", "clean, bright and natural")


def shoot_brief(direction: Any) -> ShootBrief:
    """The brief for one site, from its creative direction (duck-typed: the
    interview's CreativeDirection or the `creative_direction` dict a draft's
    theme carries)."""

    def get(key: str, default: Any = "") -> Any:
        if isinstance(direction, dict):
            return direction.get(key, default)
        return getattr(direction, key, default)

    palette = get("palette", {}) or {}
    if not isinstance(palette, dict):
        palette = palette.model_dump() if hasattr(palette, "model_dump") else {}
    dark = palette.get("mode") == "dark"
    light, grade = _LOW_KEY if dark else _AIRY
    world = str(get("image_style", "") or "warm, natural editorial photography of the trade's materials")
    lens = "50mm, shallow depth of field, eye-level or slightly above"
    if str(get("hero", "")) in {"airy_split", "full_width"}:
        lens = "35mm, straight verticals, generous negative space"
    return ShootBrief(world=world, light=light, lens=lens, grade=grade,
                      palette=tuple(str(palette.get(k, "")) for k in ("primary", "accent") if palette.get(k)))


# How the hero picture must be framed for the composition that will hold it.
HERO_FRAMING = {
    "cinematic": "Wide composition, darker calm space on the left third for a large headline.",
    "editorial_overlay": "Wide table-top composition, calm darker space on the left for a headline, "
                         "the subject on the right two-thirds.",
    "full_width": "Wide composition with calm space on the left for a headline.",
    "commerce_split": "The subject fills the frame, centred, photographed close on a dark surface.",
    "airy_split": "Architecture on the right, open bright sky and space on the left.",
    "editorial_split": "The subject fills the frame, softly lit.",
    "image_left": "The subject fills the frame, softly lit.",
    "image_right": "The subject fills the frame, softly lit.",
}


def aspect_for_hero(hero: str) -> str:
    return "16:9" if hero in {"cinematic", "editorial_overlay", "full_width"} else "4:3"


def _clean(text: str) -> str:
    """Owner words only, and nothing that reads as a number, a price or a claim."""
    return re.sub(r"\s+", " ", re.sub(r"[\d₹$]+", "", text or "")).strip(" ,.-")[:160]


def build_prompt(
    *,
    subject: str,
    purpose: str,
    truth_class: str,
    brief: ShootBrief,
    trade: str,
    hero_style: str = "",
) -> str:
    """One image prompt. Raises for a factual slot: those are never drawn."""
    if truth_class == "factual":
        raise ValueError("a factual picture is never generated — it must be the owner's own")
    subject = _clean(subject) or _clean(trade) or "the trade's materials"
    trade = _clean(trade) or "a small local business"
    if truth_class == "graphic":
        return (f"A refined, textured editorial illustration for a small business website ({trade}). "
                f"Motif: {subject}. {brief.sentence()} {_NEVER_GRAPHIC}")
    if purpose == "hero":
        framing = HERO_FRAMING.get(hero_style, "The subject fills the frame, softly lit.")
    elif purpose == "story":
        framing = "A quiet, lived-in scene of where the work happens, seen from the side."
    else:
        framing = "The subject fills the frame, centred, styled simply."
    return (f"A realistic, professional editorial photograph for a small business website ({trade}). "
            f"Subject: {subject}. {brief.sentence()} {framing} {_NEVER}")
