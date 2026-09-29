"""Regulated-category marketing checks (MK-10).

Canonical source only (Capability Universe §18.3, §20.4, §21.9, §25.1, §28.2):

- Lawyers: the marketing module is off by default. Legal-advertising rules are
  a verify-at-build item (§28.2), so this does not invent an owner bypass.
- Finance and insurance: LOCAH does not sell or advise on financial products.
  Marketing stays available and is marked restricted. No extra disclosure gate.
- Trait `minors_involved`: no marketing templates to minors (§20.4).
- Real estate, recruitment, health and finance: Meta ad targeting must be
  checked before an ad is drafted (§18.3, §28.2). That is a check, not a block
  on the business's own WhatsApp messages.
"""

from __future__ import annotations

from dataclasses import dataclass


# Taxonomy keys (catalog/taxonomy.py), not invented synonyms.
LAWYER_SUBCATEGORY = "lawyer"
FINANCE_CATEGORY = "finance_insurance"
REAL_ESTATE_CATEGORY = "real_estate"
RECRUITMENT_SUBCATEGORY = "recruitment"

TRAIT_MINORS = "minors_involved"
TRAIT_FINANCE = "finance_regulated"
TRAIT_HEALTH = "health_regulated"

# Meta special-ad categories called out for a check before targeting (§18.3).
META_CHECK_CATEGORIES = frozenset({REAL_ESTATE_CATEGORY, FINANCE_CATEGORY})
META_CHECK_SUBCATEGORIES = frozenset({RECRUITMENT_SUBCATEGORY})


@dataclass(frozen=True)
class RegulatedPolicyResult:
    allowed: bool
    # allowed | off_by_default | prohibited | restricted
    status: str
    reason: str
    # True when a Meta ad for this business must have its targeting checked.
    meta_targeting_check: bool = False


class RegulatedCategoryPolicyService:
    @staticmethod
    def evaluate(
        *,
        category_key: str | None = None,
        subcategory_key: str | None = None,
        traits: set[str] | frozenset[str] | None = None,
    ) -> RegulatedPolicyResult:
        category = (category_key or "").strip()
        subcategory = (subcategory_key or "").strip()
        held = set(traits or ())

        # §20.4 — no marketing templates to minors when the business works with them.
        if TRAIT_MINORS in held:
            return RegulatedPolicyResult(
                allowed=False,
                status="prohibited",
                reason="No marketing templates to minors.",
            )

        # §21.9 / §25.1 — marketing is off by default for lawyers.
        if subcategory == LAWYER_SUBCATEGORY:
            return RegulatedPolicyResult(
                allowed=False,
                status="off_by_default",
                reason="Marketing is off by default for lawyers.",
            )

        meta_check = (
            category in META_CHECK_CATEGORIES
            or subcategory in META_CHECK_SUBCATEGORIES
            or TRAIT_HEALTH in held
            or TRAIT_FINANCE in held
        )
        meta_note = (
            " Meta ad targeting for this category must be checked before any ad."
            if meta_check
            else ""
        )

        # §25.1 — no product selling or advice. Marketing itself is not switched off.
        if category == FINANCE_CATEGORY or TRAIT_FINANCE in held:
            return RegulatedPolicyResult(
                allowed=True,
                status="restricted",
                reason="No product selling or advice through LOCAH." + meta_note,
                meta_targeting_check=True,
            )

        if meta_check:
            return RegulatedPolicyResult(
                allowed=True,
                status="allowed",
                reason="Meta ad targeting for this category must be checked before any ad.",
                meta_targeting_check=True,
            )

        return RegulatedPolicyResult(
            allowed=True,
            status="allowed",
            reason="Category permitted for standard marketing campaigns.",
        )
