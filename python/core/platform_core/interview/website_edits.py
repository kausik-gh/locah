"""Talking to LOCAH after the website exists: edits as structured changes.

"Make the website warmer", "don't show prices", "put delivery higher", "we
also sell prawns", "that isn't our story", "use this photo first". Each is
read deterministically into a typed edit and applied to structured state —
the Blueprint's business truth or its website preferences — never to page
source. The website is then recomposed from that state (or, where the owner
has already edited the page by hand, patched, so their edits win).

The same conversation continues from onboarding; this is the seam Phase B
will add module tools to (a "take bookings from the site" request becomes a
tool action there). Here it only changes the business and its website.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from platform_core.interview import reader as rd
from platform_core.interview.models import (
    BusinessBlueprint,
    CatalogueGroup,
    CatalogueItem,
    DraftText,
    TargetState,
)

FEELS = ("warmer", "cooler", "darker", "lighter", "calmer", "bolder", "simpler", "premium", "playful")
_FEEL = {
    "warmer": re.compile(r"\b(warmer|more warm|warm(?:er)? (?:colou?rs?|feel|tones?)|cosier|cozier|earthier)\b", re.I),
    "cooler": re.compile(r"\b(cooler|colder|more blue|fresher)\b", re.I),
    "darker": re.compile(r"\b(darker|dark mode|black background|more dark)\b", re.I),
    "lighter": re.compile(r"\b(lighter|brighter|light background|white background|less dark)\b", re.I),
    "calmer": re.compile(r"\b(calmer|softer|quieter|more calm|less loud|toned? down)\b", re.I),
    "bolder": re.compile(r"\b(bolder|stronger|louder|more punch\w*|more energy|more energetic)\b", re.I),
    "simpler": re.compile(r"\b(simpler|cleaner|minimal|less busy|plainer)\b", re.I),
    "premium": re.compile(r"\b(more premium|classier|more elegant|luxur\w+|high[- ]end|upmarket)\b", re.I),
    "playful": re.compile(r"\b(more fun|playful|more colou?rful|cheerful|livelier)\b", re.I),
}
_HIDE_PRICES = re.compile(r"\b(?:don'?t|do not|no need to|stop|never)\s+(?:show|display|put|list)\s+(?:the\s+)?"
                          r"prices?\b|\bhide (?:the |all )?prices?\b|\bno prices?\b|\bremove (?:the )?prices?\b", re.I)
_SHOW_PRICES = re.compile(r"\b(?:show|display|put|add) (?:the |our )?prices?\b", re.I)
_ON_REQUEST = re.compile(r"\bprice on request\b|\b(?:ask|call) for (?:the )?price\b", re.I)
_LEAD = re.compile(r"\b(?:put|move|show|bring)\s+(?:the\s+)?(?P<what>[a-z &]+?)\s+(?:higher|up|first|to the top|"
                   r"at the top|above everything|earlier)\b", re.I)
_LEAD_TARGETS = {
    "delivery": "fulfilment_strip", "ordering": "fulfilment_strip", "how to order": "fulfilment_strip",
    "story": "about", "about": "about", "our story": "about",
    "menu": "product_showcase", "products": "product_showcase", "shop": "product_showcase",
    "range": "product_showcase", "work": "product_showcase", "projects": "product_showcase",
    "contact": "contact", "address": "contact", "location": "contact",
}
_ALSO = re.compile(r"\b(?:we|i)\s+(?:also|now)\s+(?:sell|make|offer|serve|do|stock|have)\s+(?P<what>[^.;!?\n]+)",
                   re.I)
_NOT_STORY = re.compile(r"\b(?:that|this|it)(?:'s| is)?\s*(?:isn'?t|is not|'s not|not)\s+(?:our|my|the)\s+story\b|"
                        r"\b(?:wrong|not our) story\b|\bremove (?:the |our )?story\b", re.I)
_PHOTO_FIRST = re.compile(r"\buse (?:this|that|the new|the last) (?:photo|picture|image|pic)\b.{0,20}"
                          r"\b(?:first|on top|at the top|as the cover|for the cover|main)\b|"
                          r"\bmake (?:this|that) (?:photo|picture|image) the cover\b", re.I)
_HEADLINE = re.compile(r"\b(?:change|make|set)\s+the\s+(?:headline|main line|title)\s+(?:to|say|into)\s+"
                       r"[\"“']?(?P<text>[^\"”]{3,90})[\"”']?", re.I)

# Where a new item belongs among groups the owner already has.
_KIN = {
    "seafood": re.compile(r"\b(prawns?|shrimps?|crabs?|squid|lobsters?|seer|pomfret|sardines?|mackerel|tuna|"
                          r"fish)\b", re.I),
    "chicken": re.compile(r"\b(chicken|country chicken|quail|duck|broiler)\b", re.I),
    "mutton": re.compile(r"\b(mutton|goat|lamb)\b", re.I),
    "cakes": re.compile(r"\b(cakes?|cupcakes?|brownies?|cookies?|pastr(?:y|ies))\b", re.I),
}


@dataclass
class Edits:
    feel: str = ""
    prices: str = ""  # show | from | on_request | hidden
    lead: str = ""  # section type to put right after the hero
    add_items: list[str] = field(default_factory=list)
    story_reset: bool = False
    photo_first: bool = False
    headline: str = ""

    def any(self) -> bool:
        return bool(self.feel or self.prices or self.lead or self.add_items or self.story_reset
                    or self.photo_first or self.headline)


def read(text: str) -> Edits:
    """What an owner's message asks of the website — deterministic."""
    flat = " ".join((text or "").split())
    out = Edits()
    for feel, pattern in _FEEL.items():
        if pattern.search(flat):
            out.feel = feel
            break
    if _HIDE_PRICES.search(flat):
        out.prices = "hidden"
    elif _ON_REQUEST.search(flat):
        out.prices = "on_request"
    elif _SHOW_PRICES.search(flat):
        out.prices = "show"
    lead = _LEAD.search(flat)
    if lead:
        what = lead.group("what").strip().casefold()
        out.lead = next((v for k, v in _LEAD_TARGETS.items() if k in what), "")
    also = _ALSO.search(flat)
    if also:
        out.add_items = rd.offering_names(also.group("what"))[:6]
    out.story_reset = bool(_NOT_STORY.search(flat))
    out.photo_first = bool(_PHOTO_FIRST.search(flat))
    headline = _HEADLINE.search(flat)
    if headline:
        out.headline = headline.group("text").strip(" .")
    return out


def _home(bp: BusinessBlueprint, item: str) -> CatalogueGroup | None:
    for kin, pattern in _KIN.items():
        if pattern.search(item):
            for group in bp.taxonomy.groups:
                if pattern.search(group.name) or kin in group.name.casefold():
                    return group
    return None


def apply(bp: BusinessBlueprint, edits: Edits) -> list[str]:
    """Apply the edits to structured state. Returns what changed, for the reply."""
    done: list[str] = []
    prefs = bp.website_prefs
    if edits.feel:
        prefs.feel = edits.feel
        done.append(f"feel:{edits.feel}")
    if edits.prices:
        bp.owner_choices.price_visibility = edits.prices
        done.append(f"prices:{edits.prices}")
    if edits.lead:
        prefs.lead_section = edits.lead
        done.append(f"lead:{edits.lead}")
    for name in edits.add_items:
        clean = name[:1].upper() + name[1:]
        group = _home(bp, clean)
        if group is not None:
            if all(i.name.casefold() != clean.casefold() for i in group.items):
                group.items.append(CatalogueItem(name=clean[:80]))
                done.append(f"add:{clean}:{group.name}")
            else:
                done.append(f"have:{clean}:{group.name}")
        elif all(g.name.casefold() != clean.casefold() for g in bp.taxonomy.groups):
            bp.taxonomy.groups.append(CatalogueGroup(name=clean[:80]))
            done.append(f"add:{clean}:")
        else:
            done.append(f"have:{clean}:")
    if edits.story_reset:
        bp.discovery["brand.story"] = TargetState(status="open")
        bp.website_draft.about = None
        if "about" not in bp.website_draft.dismissed:
            bp.website_draft.dismissed.append("about")
        bp.website_draft.owner_claims = []
        prefs.awaiting_story = True
        done.append("story:reset")
    if edits.photo_first:
        uploads = [m for m in bp.media_assets if m.source == "USER_UPLOAD" and m.role != "logo"]
        if uploads:
            latest = uploads[-1]
            for media in bp.media_assets:
                if media.role == "hero" and media.asset_id != latest.asset_id:
                    media.role = "gallery"
            latest.role = "hero"
            done.append("photo:hero")
    if edits.headline:
        bp.website_draft.hero_headline = DraftText(text=edits.headline[:90], provenance="owner_edited")
        done.append("headline")
    return done


def take_story(bp: BusinessBlueprint, text: str) -> bool:
    """After "that isn't our story", the owner's next message IS the story."""
    if not bp.website_prefs.awaiting_story:
        return False
    words = " ".join(text.split())
    if len(re.findall(r"\w+", words)) < 4:
        return False
    bp.discovery["brand.story"] = TargetState(status="answered", summary=words[:240], quote=words[:600])
    bp.website_draft.about = DraftText(text=words[:800], provenance="owner_edited")
    bp.website_draft.dismissed = [d for d in bp.website_draft.dismissed if d != "about"]
    bp.website_prefs.awaiting_story = False
    return True


_SAID = {
    "warmer": "warmer — softer ground, warmer colours",
    "cooler": "cooler in colour",
    "darker": "darker",
    "lighter": "lighter and brighter",
    "calmer": "calmer and quieter",
    "bolder": "bolder",
    "simpler": "simpler",
    "premium": "more premium",
    "playful": "more playful",
}


def reply(done: list[str], bp: BusinessBlueprint) -> str:
    """What LOCAH says after changing the website — plain, specific, short."""
    parts: list[str] = []
    for change in done:
        kind, _, rest = change.partition(":")
        if kind == "feel":
            parts.append(f"I've made the website {_SAID.get(rest, rest)}")
        elif kind == "prices":
            parts.append({"hidden": "prices are off the website — people will ask you",
                          "on_request": "prices now say “price on request”",
                          "show": "prices you gave now show on the website",
                          "from": "the website shows starting prices"}.get(rest, "prices updated"))
        elif kind == "lead":
            parts.append({"fulfilment_strip": "how ordering and delivery work now comes right after the top",
                          "about": "your story now comes right after the top",
                          "product_showcase": "what you offer now comes right after the top",
                          "contact": "how to reach you now comes right after the top"}.get(rest, "moved it up"))
        elif kind == "add":
            item, _, group = rest.partition(":")
            parts.append(f"added {item} to {group}" if group else f"added {item}")
        elif kind == "have":
            item, _, group = rest.partition(":")
            parts.append(f"{item} {'is' if not item.endswith('s') else 'are'} already there"
                         + (f", in {group}" if group else ""))
        elif kind == "photo":
            parts.append("that photo now leads the page")
        elif kind == "headline":
            parts.append("the headline is yours now")
    story = "story:reset" in done
    if story and not parts:
        return "Understood — I've taken that story off. What would you like people to know about you?"
    if not parts:
        return ""
    text = "Done — " + "; ".join(parts) + "."
    if story:
        text += " What would you like people to know about you instead?"
    return text + " Have a look."
