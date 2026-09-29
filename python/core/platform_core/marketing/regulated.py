"""Regulated category marketing guards (MK-10; MD §18.3, §25.1, §21.9).

Enforces canonical compliance rules:
- Legal profession (advocates, lawyers): marketing is off by default under Bar Council regulations.
- Finance and insurance: regulated marketing limits and restricted declarations.
- Minors protection (DPDP Act 2023 §9): marketing directly to minors is strictly prohibited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegulatedPolicyResult:
    allowed: bool
    status: str  # "allowed" | "requires_owner_override" | "prohibited"
    reason: str
    requires_declaration: bool = False


LEGAL_CATEGORIES = {
    "legal",
    "lawyer",
    "advocate",
    "law_firm",
    "legal_services",
    "attorney",
}

FINANCE_CATEGORIES = {
    "finance",
    "financial_services",
    "investment",
    "wealth_management",
    "lending",
    "insurance",
    "brokerage",
}

MINOR_TRAITS_OR_TAGS = {
    "minors",
    "children",
    "under_18",
    "school_students",
    "kids",
}


class RegulatedCategoryPolicyService:
    @staticmethod
    def evaluate(
        *,
        category_key: str | None = None,
        subcategory_key: str | None = None,
        business_traits: dict[str, Any] | None = None,
        target_tags: list[str] | None = None,
        owner_override: bool = False,
    ) -> RegulatedPolicyResult:
        cat = (category_key or "").lower().strip()
        subcat = (subcategory_key or "").lower().strip()
        traits = business_traits or {}
        tags = {t.lower().strip() for t in (target_tags or [])}

        # 1. DPDP Act 2023 §9: Marketing directly to minors is strictly prohibited.
        if tags & MINOR_TRAITS_OR_TAGS or traits.get("audience_is_minors") is True:
            return RegulatedPolicyResult(
                allowed=False,
                status="prohibited",
                reason="Marketing to minors is strictly prohibited under DPDP Act 2023 §9.",
            )

        # 2. Bar Council of India regulations: Advocates cannot advertise/market.
        if cat in LEGAL_CATEGORIES or subcat in LEGAL_CATEGORIES or traits.get("profession") == "advocate":
            if not owner_override:
                return RegulatedPolicyResult(
                    allowed=False,
                    status="requires_owner_override",
                    reason="Marketing is switched off by default for legal services under Bar Council of India advertising restrictions.",
                )

        # 3. Finance & Insurance: SEBI / RBI / IRDAI restrictions.
        if cat in FINANCE_CATEGORIES or subcat in FINANCE_CATEGORIES:
            return RegulatedPolicyResult(
                allowed=True,
                status="restricted",
                reason="Restricted category: financial promotions require statutory disclosures and verified customer eligibility.",
                requires_declaration=True,
            )

        return RegulatedPolicyResult(
            allowed=True,
            status="allowed",
            reason="Category permitted for standard marketing campaigns.",
        )
