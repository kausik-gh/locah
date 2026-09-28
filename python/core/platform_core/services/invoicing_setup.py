"""Setting up how a business bills (Capability Universe §14.4).

Everything here is the owner's or their CA's data: whether they are GST
registered and under which scheme, their GSTINs (one per state), the billing
registers at each location, whether prices include tax, and the rates — per
offering or per HSN/SAC, with the dates they apply. LOCAH validates shape
(a GSTIN's check character, its state) and never supplies a rate or a tax
treatment itself.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.invoicing.states import STATES, gstin_problem, normalise_gstin, state_label
from platform_core.invoicing.tax_engine import DOC_KIND_FOR_SCHEME, SCHEMES
from platform_core.models import (
    BusinessLocation,
    InvoicingDocument,
    InvoicingRegister,
    InvoicingRegistration,
    InvoicingTaxProfile,
    InvoicingTaxRate,
    Offering,
)
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService

ISSUE_ON = {
    "order_accepted": "When I accept the order",
    "order_completed": "When the order is completed (handed over or delivered)",
    "manual": "Only when I issue it myself",
}
ADVANCES = {
    "receipt_voucher": "Issue a receipt voucher when an advance is received",
    "on_bill": "Account for tax only on the final bill",
}
# The legal maximum length of a GST invoice number is checked at build
# (VB-20); numbers longer than this are flagged to the owner, not blocked.
NUMBER_LENGTH_LIMIT = 16
_CODE = re.compile(r"^[A-Z0-9]{1,8}$")
_HSN = re.compile(r"^[0-9]{2,8}$")


def _field(field: str, message: str) -> ValidationError:
    return ValidationError(message, details={"errors": [{"field": field, "message": message}], "field": field})


def local_today(tz: str | None = None) -> date:
    try:
        zone = ZoneInfo(tz or "Asia/Kolkata")
    except Exception:  # noqa: BLE001 — a bad stored zone falls back to India
        zone = ZoneInfo("Asia/Kolkata")
    return datetime.now(timezone.utc).astimezone(zone).date()


def sample_number(code: str, pad: int, today: date | None = None) -> str:
    from platform_core.services.number_series import financial_year, format_number

    return str(format_number(code, financial_year(today or local_today()), 1, pad))


def serialize_registration(r: InvoicingRegistration) -> dict[str, Any]:
    return {
        "id": str(r.id), "scheme": r.scheme, "gstin": r.gstin, "legal_name": r.legal_name,
        "trade_name": r.trade_name, "state_code": r.state_code, "state_label": state_label(r.state_code),
        "address": r.address, "composition_declaration": r.composition_declaration, "status": r.status,
        "document": DOC_KIND_FOR_SCHEME[r.scheme],
    }


def serialize_register(r: InvoicingRegister, location_name: str | None = None) -> dict[str, Any]:
    sample = sample_number(r.code, r.pad)
    return {
        "id": str(r.id), "location_id": str(r.location_id), "location_name": location_name,
        "registration_id": str(r.registration_id), "code": r.code, "name": r.name, "pad": r.pad,
        "status": r.status, "sample_number": sample, "number_length": len(sample),
        "too_long": len(sample) > NUMBER_LENGTH_LIMIT,
    }


def serialize_profile(p: InvoicingTaxProfile | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {
        "prices_include_tax": p.prices_include_tax, "round_off": p.round_off, "issue_on": p.issue_on,
        "advances_treatment": p.advances_treatment, "default_due_days": p.default_due_days,
        "terms": p.terms, "bank_details": p.bank_details,
        "ca_confirmed_at": p.ca_confirmed_at.isoformat() if p.ca_confirmed_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def serialize_rate(r: InvoicingTaxRate, title: str | None = None) -> dict[str, Any]:
    return {
        "id": str(r.id), "offering_id": str(r.offering_id) if r.offering_id else None,
        "offering_title": title, "hsn_sac": r.hsn_sac, "rate": float(r.rate),
        "effective_from": r.effective_from.isoformat(),
        "effective_to": r.effective_to.isoformat() if r.effective_to else None, "note": r.note,
    }


class InvoicingSetupService:
    # ------------------------------------------------------------------ profile
    @staticmethod
    async def profile(session: AsyncSession, business_id: uuid.UUID) -> InvoicingTaxProfile | None:
        return await session.get(InvoicingTaxProfile, business_id)

    @staticmethod
    async def save_profile(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
    ) -> InvoicingTaxProfile:
        for key in ("prices_include_tax", "round_off"):
            if not isinstance(payload.get(key), bool):
                raise _field(key, "Choose yes or no")
        issue_on = payload.get("issue_on")
        if issue_on not in ISSUE_ON:
            raise _field("issue_on", "Choose when website and WhatsApp orders get their bill")
        advances = payload.get("advances_treatment") or None
        if advances is not None and advances not in ADVANCES:
            raise _field("advances_treatment", "Unknown choice")
        due = payload.get("default_due_days")
        if due is not None and (not isinstance(due, int) or not 0 <= due <= 365):
            raise _field("default_due_days", "Between 0 and 365 days")
        profile = await session.get(InvoicingTaxProfile, business_id)
        before = serialize_profile(profile)
        now = datetime.now(timezone.utc)
        if profile is None:
            profile = InvoicingTaxProfile(business_id=business_id, prices_include_tax=payload["prices_include_tax"],
                                          round_off=payload["round_off"], issue_on=issue_on)
            session.add(profile)
        profile.prices_include_tax = payload["prices_include_tax"]
        profile.round_off = payload["round_off"]
        profile.issue_on = issue_on
        profile.advances_treatment = advances
        profile.default_due_days = due
        profile.terms = (payload.get("terms") or "").strip()[:2000] or None
        profile.bank_details = (payload.get("bank_details") or "").strip()[:1000] or None
        if payload.get("ca_confirmed"):
            profile.ca_confirmed_at = profile.ca_confirmed_at or now
        elif payload.get("ca_confirmed") is False:
            profile.ca_confirmed_at = None
        profile.updated_by = actor_id
        profile.updated_at = now
        await session.flush()
        after = serialize_profile(profile)
        await AuditService.record(session, event_type="invoicing.settings.updated", actor_identity_id=actor_id,
                                  actor_context="business", action="update", business_id=business_id,
                                  resource_type="invoicing_tax_profile", before_state=before, after_state=after)
        await OutboxService.publish(session, event_type="invoicing.settings.updated", business_id=business_id,
                                    payload={"business_id": str(business_id), "after": after})
        return profile

    # ------------------------------------------------------------------ registrations
    @staticmethod
    async def registrations(session: AsyncSession, business_id: uuid.UUID) -> list[InvoicingRegistration]:
        rows = await session.execute(
            select(InvoicingRegistration).where(InvoicingRegistration.business_id == business_id)
            .order_by(InvoicingRegistration.created_at)
        )
        return list(rows.scalars())

    @staticmethod
    def _clean_registration(payload: dict[str, Any]) -> dict[str, Any]:
        scheme = payload.get("scheme")
        if scheme not in SCHEMES:
            raise _field("scheme", "Choose regular GST, composition scheme or not registered")
        legal_name = str(payload.get("legal_name") or "").strip()
        if not legal_name:
            raise _field("legal_name", "Enter the name on the registration")
        gstin = normalise_gstin(payload.get("gstin"))
        state = str(payload.get("state_code") or "").strip()
        if scheme == "unregistered":
            gstin = None
            if state not in STATES:
                raise _field("state_code", "Choose the state the business is in")
        else:
            if not gstin:
                raise _field("gstin", "Enter the GSTIN")
            problem = gstin_problem(gstin)
            if problem:
                raise _field("gstin", problem)
            state = gstin[:2]
        declaration = str(payload.get("composition_declaration") or "").strip() or None
        if scheme == "composition" and not declaration:
            raise _field("composition_declaration",
                         "Enter the declaration printed on every bill of supply (confirm the wording with your CA)")
        return {
            "scheme": scheme, "gstin": gstin, "legal_name": legal_name[:200],
            "trade_name": (str(payload.get("trade_name") or "").strip() or None),
            "state_code": state, "address": (str(payload.get("address") or "").strip()[:500] or None),
            "composition_declaration": declaration if scheme == "composition" else None,
        }

    @staticmethod
    async def save_registration(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
        registration_id: uuid.UUID | None = None,
    ) -> InvoicingRegistration:
        clean = InvoicingSetupService._clean_registration(payload)
        existing = await InvoicingSetupService.registrations(session, business_id)
        if registration_id:
            reg = next((r for r in existing if r.id == registration_id), None)
            if reg is None:
                raise ResourceNotFound("GST registration")
            used = (await session.execute(
                select(InvoicingDocument.id).where(InvoicingDocument.business_id == business_id,
                                                   InvoicingDocument.registration_id == reg.id,
                                                   InvoicingDocument.status != "draft").limit(1)
            )).first()
            if used and (clean["gstin"] != reg.gstin or clean["scheme"] != reg.scheme):
                # Issued bills carry this GSTIN; a new registration keeps history honest.
                raise ConflictError("Bills were already issued under this registration. Add a new registration "
                                    "for a new GSTIN or scheme instead of changing this one.")
        else:
            reg = InvoicingRegistration(business_id=business_id, **clean)
        others = [r for r in existing if r.id != getattr(reg, "id", None) and r.status == "active"]
        if clean["scheme"] == "unregistered" and others:
            raise ConflictError("A business that is not registered has a single registration row")
        if any(r.scheme == "unregistered" for r in others):
            raise ConflictError("Remove the 'not registered' entry before adding a GSTIN")
        if clean["gstin"] and any(r.gstin == clean["gstin"] for r in others):
            raise _field("gstin", "That GSTIN is already added")
        for key, value in clean.items():
            setattr(reg, key, value)
        reg.updated_at = datetime.now(timezone.utc)
        session.add(reg)
        await session.flush()
        await AuditService.record(session, event_type="invoicing.settings.updated", actor_identity_id=actor_id,
                                  actor_context="business", action="registration.save", business_id=business_id,
                                  resource_type="invoicing_registration", resource_id=reg.id,
                                  after_state=serialize_registration(reg))
        return reg

    # ------------------------------------------------------------------ registers
    @staticmethod
    async def registers(session: AsyncSession, business_id: uuid.UUID) -> list[tuple[InvoicingRegister, str]]:
        rows = await session.execute(
            select(InvoicingRegister, BusinessLocation.name)
            .join(BusinessLocation, BusinessLocation.id == InvoicingRegister.location_id)
            .where(InvoicingRegister.business_id == business_id)
            .order_by(BusinessLocation.name, InvoicingRegister.code)
        )
        return [(r, n) for r, n in rows.all()]

    @staticmethod
    async def save_register(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
        register_id: uuid.UUID | None = None,
    ) -> InvoicingRegister:
        code = str(payload.get("code") or "").strip().upper()
        if not _CODE.match(code):
            raise _field("code", "1–8 capital letters or digits, e.g. CHN1")
        name = str(payload.get("name") or "").strip() or f"Counter {code}"
        pad = payload.get("pad", 5)
        if not isinstance(pad, int) or not 3 <= pad <= 8:
            raise _field("pad", "Between 3 and 8 digits")
        try:
            location_id = uuid.UUID(str(payload.get("location_id")))
            registration_id = uuid.UUID(str(payload.get("registration_id")))
        except ValueError as exc:
            raise _field("location_id", "Choose a location and a registration") from exc
        location = await session.get(BusinessLocation, location_id)
        if location is None or location.business_id != business_id or location.deleted_at is not None:
            raise _field("location_id", "Choose one of your locations")
        registration = await session.get(InvoicingRegistration, registration_id)
        if registration is None or registration.business_id != business_id:
            raise _field("registration_id", "Choose one of your GST registrations")
        if register_id:
            reg = await session.get(InvoicingRegister, register_id)
            if reg is None or reg.business_id != business_id:
                raise ResourceNotFound("Register")
            used = (await session.execute(
                select(InvoicingDocument.id).where(InvoicingDocument.register_id == reg.id,
                                                   InvoicingDocument.status != "draft").limit(1)
            )).first()
            if used and (reg.code != code or reg.registration_id != registration_id or reg.pad != pad):
                raise ConflictError("Bills were already numbered from this register; its code, padding and "
                                    "registration are fixed. Add a new register instead.")
        else:
            reg = InvoicingRegister(business_id=business_id)
        dup = (await session.execute(
            select(InvoicingRegister.id).where(InvoicingRegister.business_id == business_id,
                                               InvoicingRegister.registration_id == registration_id,
                                               InvoicingRegister.code == code,
                                               InvoicingRegister.id != (register_id or uuid.uuid4()))
        )).first()
        if dup:
            raise _field("code", "Another register under this GSTIN already uses that code")
        reg.location_id = location_id
        reg.registration_id = registration_id
        reg.code, reg.name, reg.pad = code, name[:80], pad
        if payload.get("status") in ("active", "inactive"):
            reg.status = payload["status"]
        reg.updated_at = datetime.now(timezone.utc)
        session.add(reg)
        await session.flush()
        await AuditService.record(session, event_type="invoicing.settings.updated", actor_identity_id=actor_id,
                                  actor_context="business", action="register.save", business_id=business_id,
                                  resource_type="invoicing_register", resource_id=reg.id,
                                  after_state=serialize_register(reg))
        return reg

    @staticmethod
    async def register_for_location(
        session: AsyncSession, business_id: uuid.UUID, location_id: uuid.UUID,
    ) -> InvoicingRegister | None:
        """The location's first active register — where its website and WhatsApp orders are billed."""
        row = (await session.execute(
            select(InvoicingRegister).where(InvoicingRegister.business_id == business_id,
                                            InvoicingRegister.location_id == location_id,
                                            InvoicingRegister.status == "active")
            .order_by(InvoicingRegister.created_at).limit(1)
        )).scalars().first()
        return row

    # ------------------------------------------------------------------ overview
    @staticmethod
    async def overview(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        profile = await InvoicingSetupService.profile(session, business_id)
        regs = await InvoicingSetupService.registrations(session, business_id)
        registers = await InvoicingSetupService.registers(session, business_id)
        locations = list((await session.execute(
            select(BusinessLocation).where(BusinessLocation.business_id == business_id,
                                           BusinessLocation.deleted_at.is_(None))
            .order_by(BusinessLocation.is_primary.desc(), BusinessLocation.name)
        )).scalars())
        covered = {r.location_id for r, _ in registers if r.status == "active"}
        needs: list[str] = []
        if profile is None:
            needs.append("Choose how you bill (prices with or without GST, round-off, when orders are billed)")
        if not regs:
            needs.append("Add your GST registration, or say you are not registered")
        for loc in locations:
            if loc.id not in covered:
                needs.append(f"Add a billing register for {loc.name}")
        return {
            "profile": serialize_profile(profile),
            "registrations": [serialize_registration(r) for r in regs],
            "registers": [serialize_register(r, n) for r, n in registers],
            "locations": [{"id": str(loc.id), "name": loc.name, "is_primary": loc.is_primary,
                           "internal_code": loc.internal_code} for loc in locations],
            "states": [{"code": k, "name": v} for k, v in STATES.items()],
            "issue_on_choices": ISSUE_ON, "advances_choices": ADVANCES,
            "needs": needs, "ready": not needs,
            "confirm_with_ca": [
                "Whether your prices include GST",
                "How tax on advances is handled",
                "Which rate applies where there is a choice (for example restaurant service)",
                "Reverse charge on a bill",
                "The wording of the composition declaration",
            ],
        }


class TaxRateService:
    """Rates as data with effective dates (§14.4). The newest rate that covers
    the bill date wins: an item's own dated rate, then the longest matching
    HSN/SAC prefix, then the rate typed on the item. No rate is ever invented."""

    @staticmethod
    async def list_rates(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await session.execute(
            select(InvoicingTaxRate, Offering.title)
            .outerjoin(Offering, Offering.id == InvoicingTaxRate.offering_id)
            .where(InvoicingTaxRate.business_id == business_id)
            .order_by(InvoicingTaxRate.hsn_sac.nulls_last(), Offering.title, InvoicingTaxRate.effective_from.desc())
        )
        return [serialize_rate(r, t) for r, t in rows.all()]

    @staticmethod
    async def add(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
    ) -> InvoicingTaxRate:
        hsn = str(payload.get("hsn_sac") or "").strip() or None
        offering_id = payload.get("offering_id") or None
        if bool(hsn) == bool(offering_id):
            raise _field("hsn_sac", "Give either an HSN/SAC code or an item")
        if hsn and not _HSN.match(hsn):
            raise _field("hsn_sac", "HSN/SAC codes are 2 to 8 digits")
        if offering_id:
            offering = await session.get(Offering, uuid.UUID(str(offering_id)))
            if offering is None or offering.business_id != business_id:
                raise _field("offering_id", "Choose one of your items")
            offering_id = offering.id
        try:
            rate = Decimal(str(payload.get("rate")))
        except Exception as exc:  # noqa: BLE001
            raise _field("rate", "Enter the rate as a number") from exc
        if not Decimal("0") <= rate <= Decimal("100") or rate != rate.quantize(Decimal("0.01")):
            raise _field("rate", "A rate between 0 and 100, up to two decimals")
        try:
            start = date.fromisoformat(str(payload.get("effective_from")))
        except ValueError as exc:
            raise _field("effective_from", "Choose the date the rate applies from") from exc
        existing = list((await session.execute(
            select(InvoicingTaxRate).where(
                InvoicingTaxRate.business_id == business_id,
                (InvoicingTaxRate.hsn_sac == hsn) if hsn else (InvoicingTaxRate.offering_id == offering_id),
            ).with_for_update()
        )).scalars())
        for r in existing:
            if r.effective_from == start:
                raise _field("effective_from", "A rate already starts on that date; remove it first")
            if r.effective_from < start and (r.effective_to is None or r.effective_to >= start):
                # The previous rate ends the day before the new one starts.
                r.effective_to = start - timedelta(days=1)
        later = [r.effective_from for r in existing if r.effective_from > start]
        row = InvoicingTaxRate(
            business_id=business_id, offering_id=offering_id, hsn_sac=hsn, rate=rate, effective_from=start,
            effective_to=(min(later) - timedelta(days=1)) if later else None,
            note=(str(payload.get("note") or "").strip()[:300] or None), created_by=actor_id,
        )
        session.add(row)
        await session.flush()
        await AuditService.record(session, event_type="invoicing.tax_rates.changed", actor_identity_id=actor_id,
                                  actor_context="business", action="add", business_id=business_id,
                                  resource_type="invoicing_tax_rate", resource_id=row.id,
                                  after_state=serialize_rate(row))
        return row

    @staticmethod
    async def remove(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, rate_id: uuid.UUID) -> None:
        row = await session.get(InvoicingTaxRate, rate_id)
        if row is None or row.business_id != business_id:
            raise ResourceNotFound("Tax rate")
        before = serialize_rate(row)
        await session.delete(row)
        await session.flush()
        # Issued bills keep the rate they were issued with (lines are snapshots).
        await AuditService.record(session, event_type="invoicing.tax_rates.changed", actor_identity_id=actor_id,
                                  actor_context="business", action="remove", business_id=business_id,
                                  resource_type="invoicing_tax_rate", resource_id=rate_id, before_state=before)

    @staticmethod
    async def resolve(
        session: AsyncSession, business_id: uuid.UUID, items: list[tuple[uuid.UUID | None, str | None, Any]],
        on: date,
    ) -> list[Decimal | None]:
        """For each (offering_id, hsn_sac, rate typed on the item): the rate that applies on `on`."""
        offering_ids = {o for o, _, _ in items if o}
        rows = list((await session.execute(
            select(InvoicingTaxRate).where(
                InvoicingTaxRate.business_id == business_id,
                InvoicingTaxRate.effective_from <= on,
                (InvoicingTaxRate.effective_to.is_(None)) | (InvoicingTaxRate.effective_to >= on),
            )
        )).scalars())
        by_offering = {r.offering_id: Decimal(str(r.rate)) for r in rows if r.offering_id in offering_ids}
        by_hsn = sorted(((r.hsn_sac, Decimal(str(r.rate))) for r in rows if r.hsn_sac),
                        key=lambda x: -len(x[0] or ""))
        out: list[Decimal | None] = []
        for offering_id, hsn, typed in items:
            if offering_id and offering_id in by_offering:
                out.append(by_offering[offering_id])
                continue
            match = next((rate for code, rate in by_hsn if hsn and code and hsn.startswith(code)), None)
            if match is not None:
                out.append(match)
            elif typed is not None:
                out.append(Decimal(str(typed)))
            else:
                out.append(None)
        return out
