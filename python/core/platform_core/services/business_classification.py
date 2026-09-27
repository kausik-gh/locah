"""The kind of business, how it operates, and what LOCAH recommends for it
(Capability Universe §4, §5, §21, §22, §24 #1–2).

* Classification (category, subcategory, org shape) lives on `businesses`.
* Operating traits live in `business_traits`: seeded from the subcategory's
  defaults, then switched on or off by the owner. An owner's choice is never
  overwritten by a re-seed.
* Recommendations are a pure function of those facts
  (platform_core.catalog.recommendation) joined with real readiness
  (platform_core.services.module_readiness) — never a module grant.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.catalog import taxonomy
from platform_core.catalog.modules import MODULES
from platform_core.catalog.recommendation import recommend
from platform_core.exceptions import ValidationError
from platform_core.models import Business, BusinessTrait
from platform_core.services.audit import AuditService
from platform_core.services.module_readiness import readiness
from platform_core.services.outbox import OutboxService

TRAIT_SOURCES = frozenset({"default", "owner", "ai_suggested_confirmed"})

# Owner-facing words for every trait (the owner never sees a key).
TRAIT_LABELS: dict[str, str] = {
    "b2c": "I sell to people", "b2b": "I sell to businesses",
    "sells_products": "I sell products", "sells_services": "I sell services",
    "sells_access": "People pay for access or membership",
    "order_led": "Customers place orders", "booking_led": "Customers book a time or date",
    "quote_led": "I send quotes before selling", "enquiry_led": "Most business starts with an enquiry",
    "subscription_led": "Customers subscribe or renew", "project_led": "My work runs as projects",
    "donation_led": "I receive donations",
    "appointment": "Appointments", "table": "Table reservations", "stay": "Stays / rooms",
    "class": "Classes or batches", "rental": "Rentals", "site_visit": "Site visits",
    "event_date": "Event dates",
    "walk_in": "Customers walk in", "pickup": "Customers pick up", "local_delivery": "I deliver locally",
    "shipping": "I ship across India", "on_site_service": "I work at the customer's place",
    "digital": "I deliver online",
    "stock_tracked": "I keep stock", "perishable": "My stock goes bad quickly",
    "weight_based": "I sell by weight", "variant_based": "Items come in sizes or colours",
    "serialised": "Items have serial numbers", "made_to_order": "I make things to order",
    "ingredient_based": "I make items from ingredients or materials",
    "provider_based": "Customers choose a named person (stylist, doctor, trainer)",
    "field_team": "My team works in the field", "shift_staff": "My staff work in shifts",
    "gst_registered": "I am GST registered", "composition_scheme": "I am on the GST composition scheme",
    "food_licensed": "I need a food licence (FSSAI)", "health_regulated": "Healthcare rules apply",
    "finance_regulated": "Financial regulations apply", "minors_involved": "I work with children",
    "portfolio_led": "I win work by showing past work", "digital_only": "I have no public address",
    "nonprofit": "I am a nonprofit",
}

GROUP_LABELS: dict[str, str] = {
    "buyer": "Who buys", "offer": "What you offer", "transact": "How people buy",
    "booking_kind": "What people book", "fulfilment": "How it reaches them",
    "stock": "Stock", "people": "Your people", "regulated": "Rules that apply",
    "presentation": "How you present yourself",
}

ORG_SHAPE_LABELS: dict[str, str] = {
    "solo": "Just me", "team": "A team", "multi_location": "Several locations",
    "franchise_brand": "A franchise brand", "franchise_outlet": "A franchise outlet",
    "enterprise": "A large organisation with departments",
}


def _subcategory(business: Business) -> tuple[Any, Any] | None:
    found: tuple[Any, Any] | None = taxonomy.resolve(business.category_key, business.subcategory_key)
    return found


def default_traits(business: Business) -> frozenset[str]:
    found = _subcategory(business)
    return frozenset(found[1].traits) if found else frozenset()


def default_org_shape(business: Business) -> str:
    from platform_core.catalog.families import BY_KEY
    from platform_core.catalog.recommendation import family_key_for

    found = _subcategory(business)
    if not found:
        return "team"
    fam = BY_KEY.get(family_key_for(found[1].key, found[1].playbook) or "")
    return "solo" if fam and fam.people.lower().startswith(("solo", "often solo")) else "team"


class BusinessClassificationService:
    # ------------------------------------------------------------- reading

    @staticmethod
    async def trait_rows(session: AsyncSession, business_id: uuid.UUID) -> list[BusinessTrait]:
        rows = await session.execute(
            select(BusinessTrait).where(BusinessTrait.business_id == business_id)
        )
        return list(rows.scalars().all())

    @staticmethod
    async def effective_traits(session: AsyncSession, business: Business) -> frozenset[str]:
        rows = await BusinessClassificationService.trait_rows(session, business.id)
        if not rows:
            return default_traits(business)
        return frozenset(r.trait_key for r in rows if r.enabled)

    @staticmethod
    async def get(session: AsyncSession, business: Business) -> dict[str, Any]:
        rows = {r.trait_key: r for r in await BusinessClassificationService.trait_rows(session, business.id)}
        defaults = default_traits(business)
        effective = frozenset(k for k, r in rows.items() if r.enabled) if rows else defaults
        found = _subcategory(business)
        groups = []
        for group, keys in taxonomy.TRAIT_GROUPS.items():
            groups.append({
                "key": group,
                "label": GROUP_LABELS[group],
                "traits": [
                    {
                        "key": k,
                        "label": TRAIT_LABELS[k],
                        "on": k in effective,
                        "default": k in defaults,
                        "source": rows[k].source if k in rows else ("default" if k in defaults else None),
                    }
                    for k in keys
                ],
            })
        return {
            "category_key": business.category_key,
            "subcategory_key": business.subcategory_key,
            "category_label": found[0].label if found else None,
            "subcategory_label": found[1].label if found else None,
            "org_shape": business.org_shape or default_org_shape(business),
            "org_shape_is_default": business.org_shape is None,
            "org_shapes": [{"key": k, "label": v} for k, v in ORG_SHAPE_LABELS.items()],
            "traits": sorted(effective),
            "default_traits": sorted(defaults),
            "trait_groups": groups,
            "taxonomy_version": taxonomy.TAXONOMY_VERSION,
        }

    # ------------------------------------------------------------- writing

    @staticmethod
    async def _seed_defaults(session: AsyncSession, business: Business) -> None:
        """Replace default-sourced rows with the subcategory's defaults.

        Owner and confirmed-AI rows (on or off) are kept untouched.
        """
        rows = {r.trait_key: r for r in await BusinessClassificationService.trait_rows(session, business.id)}
        await session.execute(
            delete(BusinessTrait).where(
                BusinessTrait.business_id == business.id, BusinessTrait.source == "default"
            )
        )
        for key in sorted(default_traits(business)):
            if key in rows and rows[key].source != "default":
                continue
            session.add(BusinessTrait(business_id=business.id, trait_key=key, enabled=True, source="default"))
        await session.flush()

    @staticmethod
    async def set_classification(
        session: AsyncSession,
        business: Business,
        *,
        category_key: str,
        subcategory_key: str | None,
        actor_id: uuid.UUID | None,
        correlation_id: str | None = None,
        audit: bool = True,
    ) -> dict[str, Any]:
        found = taxonomy.resolve(category_key, subcategory_key or None)
        if not found:
            raise ValidationError(
                "Unknown kind of business", details={"field": "subcategory_key"}
            )
        category, sub = found
        before = {"category_key": business.category_key, "subcategory_key": business.subcategory_key}
        sub_key = sub.key if sub.key != category.key else None  # a category alone
        changed = (business.category_key, business.subcategory_key) != (category.key, sub_key)
        business.category_key = category.key
        business.subcategory_key = sub_key
        meta = dict(business.metadata_ or {})
        meta["classification"] = {**(meta.get("classification") or {}),
                                  "category_key": category.key, "subcategory_key": sub_key or ""}
        business.metadata_ = meta
        await session.flush()
        if changed or not await BusinessClassificationService.trait_rows(session, business.id):
            await BusinessClassificationService._seed_defaults(session, business)
        if changed and audit and actor_id is not None:
            await AuditService.record(
                session,
                event_type="business.classification.changed",
                actor_identity_id=actor_id,
                actor_context="business",
                business_id=business.id,
                resource_type="business",
                resource_id=business.id,
                action="classify",
                before_state=before,
                after_state={"category_key": category.key, "subcategory_key": sub_key},
            )
            await OutboxService.publish(
                session,
                event_type="business.classification.changed",
                business_id=business.id,
                payload={"category_key": category.key, "subcategory_key": sub_key},
                correlation_id=correlation_id,
            )
        return await BusinessClassificationService.get(session, business)

    @staticmethod
    async def set_org_shape(
        session: AsyncSession, business: Business, *, org_shape: str, actor_id: uuid.UUID
    ) -> None:
        if org_shape not in taxonomy.ORG_SHAPES:
            raise ValidationError("Unknown organisation shape", details={"field": "org_shape"})
        before = business.org_shape
        business.org_shape = org_shape
        await session.flush()
        await AuditService.record(
            session,
            event_type="business.org_shape.changed",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business.id,
            resource_type="business",
            resource_id=business.id,
            action="update",
            before_state={"org_shape": before},
            after_state={"org_shape": org_shape},
        )

    @staticmethod
    async def set_traits(
        session: AsyncSession,
        business: Business,
        *,
        changes: dict[str, bool],
        actor_id: uuid.UUID,
        source: str = "owner",
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        unknown = sorted(set(changes) - taxonomy.TRAITS)
        if unknown:
            raise ValidationError("Unknown trait", details={"field": "traits", "unknown": unknown})
        if source not in TRAIT_SOURCES - {"default"}:
            raise ValidationError("Traits can only be set by the owner or confirmed", details={"field": "source"})
        rows = {r.trait_key: r for r in await BusinessClassificationService.trait_rows(session, business.id)}
        if not rows:
            await BusinessClassificationService._seed_defaults(session, business)
            rows = {r.trait_key: r for r in await BusinessClassificationService.trait_rows(session, business.id)}
        before = sorted(k for k, r in rows.items() if r.enabled)
        now = datetime.now(timezone.utc)
        for key, on in changes.items():
            row = rows.get(key)
            if row is None:
                session.add(BusinessTrait(business_id=business.id, trait_key=key, enabled=bool(on),
                                          source=source, set_by=actor_id))
            else:
                row.enabled = bool(on)
                row.source = source
                row.set_by = actor_id
                row.updated_at = now
        await session.flush()
        after = sorted(await BusinessClassificationService.effective_traits(session, business))
        if before != after:
            await AuditService.record(
                session,
                event_type="business.traits.changed",
                actor_identity_id=actor_id,
                actor_context="business",
                business_id=business.id,
                resource_type="business",
                resource_id=business.id,
                action="update",
                before_state={"traits": before},
                after_state={"traits": after},
            )
            await OutboxService.publish(
                session,
                event_type="business.traits.changed",
                business_id=business.id,
                payload={"added": sorted(set(after) - set(before)), "removed": sorted(set(before) - set(after))},
                correlation_id=correlation_id,
            )
        return await BusinessClassificationService.get(session, business)

    # ------------------------------------------------------------- recommending

    @staticmethod
    async def recommendations(session: AsyncSession, business: Business) -> dict[str, Any]:
        traits = await BusinessClassificationService.effective_traits(session, business)
        found = _subcategory(business)
        rec = recommend(
            subcategory_key=found[1].key if found else None,
            playbook=found[1].playbook if found else None,
            traits=traits,
            default_traits=default_traits(business),
        )
        data: dict[str, Any] = rec.as_dict()
        modules: list[dict[str, Any]] = data["modules"]
        keys = [m["module"] for m in modules]
        ready = await readiness(session, business.id, [k for k in keys if k in MODULES])
        for m in modules:
            info = MODULES.get(m["module"])
            m.update({
                "does": info.does if info else "",
                "customer_can": list(info.customer_can) if info else [],
                "staff_can": list(info.staff_can) if info else [],
                "surfaces": list(info.surfaces) if info else [],
                "readiness": ready.get(m["module"]),
            })
        data["traits"] = sorted(traits)
        return data
