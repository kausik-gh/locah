"""Verified reviews and their moderation (Capability Universe §17; §26.3 P1-09).

* Only a completed interaction invites a review — a delivered / completed
  order or a completed booking (§17.1; a membership period with a check-in
  arrives with attendance in P2, a closed job card with jobs in P5). One
  review per interaction, written within 30 days, from the invitation link
  (its hash is stored, like bill and khata links). Rating 1–5, text, up to
  three photos; every LOCAH review is "Verified".
* The business replies publicly, reports a review with a reason, and chooses
  which reviews its website features. It never deletes or edits one — there
  is no such path here, and the database refuses it (§17.5).
* A LOCAH moderator works the report queue: dismiss, or remove for a listed
  violation (reason logged, the reviewer told, one appeal), and may only redact
  personal data.
* The average is always the mean of every published review, featured or not.
* A 1–2 star review puts the customer, with their contact, in the owner's
  "Needs you now"; only the reviewer can then update their review (§17.3).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.models import (
    Booking,
    Business,
    CustomerContact,
    Review,
    ReviewInvitation,
    ReviewModerationLog,
    ReviewPhoto,
    ReviewReport,
    SalesOrder,
)
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService

IST = ZoneInfo("Asia/Kolkata")
WINDOW = timedelta(days=30)
MAX_PHOTOS = 3
MAX_PHOTO_BYTES = 1_500_000
MAX_FEATURED = 6
VIOLATIONS: dict[str, str] = {
    "fake": "No genuine experience (spam or fake)",
    "abuse": "Abuse or hate",
    "personal_data": "Personal data",
    "off_topic": "Off-topic",
    "conflict_of_interest": "Conflict of interest (staff, owner or competitor)",
    "illegal": "Illegal content",
}
REDACTED = "[personal details removed]"
SOURCE_WORDS = {"order": "Verified order", "booking": "Verified booking", "membership": "Verified member",
                "job": "Verified job"}
_MAGIC = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _err(field: str, message: str) -> ValidationError:
    return ValidationError(message, details={"errors": [{"field": field, "message": message}]})


def review_token(business_id: uuid.UUID, invitation_id: uuid.UUID) -> str:
    """The invitation's link credential, derived so it can be re-sent without storing it."""
    from platform_core.services.invoicing import _link_secret

    mac = hmac.new(_link_secret().encode(), f"review:{business_id}:{invitation_id}".encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode().rstrip("=")[:32]


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def display_name(name: str | None) -> str:
    """'Priya Sundaram' → 'Priya S.'; a phone number or nothing → 'A verified customer'."""
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if not parts or parts[0].startswith("+") or parts[0].isdigit():
        return "A verified customer"
    first = parts[0][:30]
    return f"{first} {parts[-1][0].upper()}." if len(parts) > 1 else first


def _avg(total: int, n: int) -> float | None:
    if not n:
        return None
    return float((Decimal(total) / Decimal(n)).quantize(Decimal("0.01"), ROUND_HALF_UP))


async def _as(session: AsyncSession, actor: str) -> None:
    """Which path is changing a review, for the database's own guard (migration P1-09)."""
    await session.execute(text("SELECT set_config('app.review_actor', :a, true)"), {"a": actor})


class ReviewService:
    # ------------------------------------------------------------------ invitations
    @staticmethod
    async def invite(session: AsyncSession, business_id: uuid.UUID, *, source_type: str, source_id: uuid.UUID,
                     contact_id: uuid.UUID | None, label: str, completed_at: datetime) -> ReviewInvitation | None:
        """One invitation per completed interaction; nothing without a customer to ask."""
        if contact_id is None:
            return None
        existing = (await session.execute(select(ReviewInvitation).where(
            ReviewInvitation.business_id == business_id, ReviewInvitation.source_type == source_type,
            ReviewInvitation.source_id == source_id))).scalars().first()
        if existing is not None:
            return existing
        inv_id = uuid.uuid4()
        inv = ReviewInvitation(id=inv_id, business_id=business_id, source_type=source_type, source_id=source_id,
                               customer_contact_id=contact_id, label=label[:200], completed_at=completed_at,
                               expires_at=completed_at + WINDOW, token_hash=_hash(review_token(business_id, inv_id)))
        session.add(inv)
        await session.flush()
        await OutboxService.publish(session, event_type="review.invited", business_id=business_id,
                                    payload={"business_id": str(business_id), "invitation_id": str(inv.id),
                                             "source_type": source_type, "source_id": str(source_id),
                                             "customer_contact_id": str(contact_id)})
        from platform_core.automation import AutomationEngine
        from platform_core.services.consumer_activity import ConsumerActivityService

        await AutomationEngine.schedule(session, business_id, ladder_key="review.request", entity_id=inv.id,
                                        anchor=completed_at, period_key=str(inv.id), context={}, now=_now())
        # §17.1: a prompt in My Activity for a customer with a LOCAH account.
        slug = (await session.execute(text("SELECT slug FROM businesses WHERE id = :b"),
                                      {"b": str(business_id)})).scalar()
        await ConsumerActivityService.record_for_customer_contact(
            session, business_id=business_id, customer_contact_id=contact_id, activity_type="review.requested",
            resource_type="review_invitation", resource_id=inv.id,
            summary={"label": inv.label, "expires_at": inv.expires_at.isoformat(), "business_slug": slug})
        return inv

    @staticmethod
    async def _answered(session: AsyncSession, inv: ReviewInvitation, how: str) -> None:
        """My Activity stops asking once the customer reviewed or said no thanks."""
        from platform_core.services.consumer_activity import ConsumerActivityService

        await ConsumerActivityService.record_for_customer_contact(
            session, business_id=inv.business_id, customer_contact_id=inv.customer_contact_id,
            activity_type=f"review.{how}", resource_type="review_invitation", resource_id=inv.id,
            summary={"label": inv.label})

    @staticmethod
    async def link(session: AsyncSession, inv: ReviewInvitation) -> str:
        from platform_core.site_urls import business_site_url

        slug = (await session.execute(text("SELECT slug FROM businesses WHERE id = :b"),
                                      {"b": str(inv.business_id)})).scalar()
        return str(business_site_url(str(slug), f"/review/{review_token(inv.business_id, inv.id)}"))

    @staticmethod
    async def source_completed(session: AsyncSession, inv: ReviewInvitation) -> bool:
        """§17.5: re-checked when the review is written — the interaction must still be complete."""
        if inv.source_type == "order":
            order = await session.get(SalesOrder, inv.source_id)
            return order is not None and order.business_id == inv.business_id and order.status == "completed" \
                and order.customer_contact_id == inv.customer_contact_id
        if inv.source_type == "booking":
            booking = await session.get(Booking, inv.source_id)
            return booking is not None and booking.business_id == inv.business_id \
                and booking.status == "completed" and booking.customer_contact_id == inv.customer_contact_id
        return False

    # ------------------------------------------------------------------ the reviewer's link
    @staticmethod
    async def _by_token(session: AsyncSession, slug: str, token: str) -> tuple[ReviewInvitation, Business]:
        if not 16 <= len(token or "") <= 64:
            raise ResourceNotFound("Review link")
        await session.execute(text("SELECT set_config('app.current_review_token', :h, true)"), {"h": _hash(token)})
        inv = (await session.execute(select(ReviewInvitation).where(
            ReviewInvitation.token_hash == _hash(token)).execution_options(populate_existing=True))).scalars().first()
        if inv is None:
            raise ResourceNotFound("Review link")
        await session.execute(text("SELECT set_config('app.current_business_id', :b, true)"),
                              {"b": str(inv.business_id)})
        business = await session.get(Business, inv.business_id)
        if business is None or business.slug != slug:
            raise ResourceNotFound("Review link")
        return inv, business

    @staticmethod
    async def _review_for(session: AsyncSession, inv: ReviewInvitation, *, lock: bool = False) -> Review | None:
        q = select(Review).where(Review.invitation_id == inv.id)
        if lock:
            q = q.with_for_update()
        return (await session.execute(q.execution_options(populate_existing=True))).scalars().first()

    @staticmethod
    async def reviewer_view(session: AsyncSession, slug: str, token: str) -> dict[str, Any]:
        inv, business = await ReviewService._by_token(session, slug, token)
        review = await ReviewService._review_for(session, inv)
        now = _now()
        state = ("written" if review else "declined" if inv.declined_at else
                 "expired" if now > inv.expires_at else "open")
        out: dict[str, Any] = {
            "business_name": business.display_name, "label": inv.label, "source_type": inv.source_type,
            "verified": SOURCE_WORDS.get(inv.source_type, "Verified"), "state": state,
            "expires_at": inv.expires_at.isoformat(), "violations": VIOLATIONS, "review": None,
        }
        if review is not None:
            out["review"] = {**await ReviewService.serialize(session, review, public=False, token=token),
                             "can_appeal": review.status == "removed" and review.appeal_status is None}
        return out

    @staticmethod
    def _photos_in(raw: list[dict[str, Any]] | None) -> list[tuple[str, bytes]]:
        out = []
        for i, p in enumerate(raw or []):
            media_type = str(p.get("media_type") or "").lower()
            if media_type not in _MAGIC:
                raise _err(f"photos.{i}", "Photos can be JPEG, PNG or WebP")
            try:
                data = base64.b64decode(str(p.get("data_base64") or ""), validate=True)
            except (binascii.Error, ValueError):
                raise _err(f"photos.{i}", "That photo could not be read") from None
            if not data or len(data) > MAX_PHOTO_BYTES:
                raise _err(f"photos.{i}", "Each photo can be up to 1.5 MB")
            if not any(data.startswith(m) for m in _MAGIC[media_type]) or (
                    media_type == "image/webp" and data[8:12] != b"WEBP"):
                raise _err(f"photos.{i}", "That file is not the picture it says it is")
            out.append((media_type, data))
        return out

    @staticmethod
    def _clean(rating: Any, body: Any) -> tuple[int, str | None]:
        try:
            r = int(rating)
        except (TypeError, ValueError):
            raise _err("rating", "Choose 1 to 5 stars") from None
        if not 1 <= r <= 5:
            raise _err("rating", "Choose 1 to 5 stars")
        b = str(body or "").strip() or None
        if b is not None and len(b) > 2000:
            raise _err("body", "Keep it under 2,000 characters")
        return r, b

    @staticmethod
    async def write(session: AsyncSession, slug: str, token: str, *, rating: Any, body: Any,
                    photos: list[dict[str, Any]] | None) -> dict[str, Any]:
        """The customer's review, from their invitation (§17.1, §17.5)."""
        inv, business = await ReviewService._by_token(session, slug, token)
        if await ReviewService._review_for(session, inv, lock=True) is not None:
            raise ConflictError("You have already reviewed this — you can change your review instead")
        if inv.declined_at is not None:
            raise ConflictError("You said no thanks to reviewing this")
        if _now() > inv.expires_at:
            raise ConflictError("Reviews can be written within 30 days of your visit or order")
        if not await ReviewService.source_completed(session, inv):
            raise ValidationError("Only a completed order or booking can be reviewed",
                                  details={"errors": [{"field": "source", "message": "Not completed"}]})
        r, b = ReviewService._clean(rating, body)
        pics = ReviewService._photos_in(photos)
        if len(pics) > MAX_PHOTOS:
            raise _err("photos", "Up to 3 photos")
        contact = await session.get(CustomerContact, inv.customer_contact_id)
        review = Review(business_id=inv.business_id, invitation_id=inv.id, source_type=inv.source_type,
                        source_id=inv.source_id, customer_contact_id=inv.customer_contact_id,
                        reviewer_name=display_name(contact.display_name if contact else None), rating=r, body=b)
        session.add(review)
        await session.flush()
        for i, (media_type, data) in enumerate(pics):
            session.add(ReviewPhoto(business_id=inv.business_id, review_id=review.id, media_type=media_type,
                                    size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), content=data,
                                    sort_order=i))
        await session.flush()
        await ReviewService._after_change(session, review, "review.published", business=business)
        await ReviewService._answered(session, inv, "written")
        return await ReviewService.reviewer_view(session, slug, token)

    @staticmethod
    async def update_by_reviewer(session: AsyncSession, slug: str, token: str, *, rating: Any, body: Any,
                                 remove_photo_ids: list[str] | None,
                                 photos: list[dict[str, Any]] | None) -> dict[str, Any]:
        """Only the reviewer changes their review (§17.2, §17.3) — e.g. after the owner put things right."""
        inv, business = await ReviewService._by_token(session, slug, token)
        review = await ReviewService._review_for(session, inv, lock=True)
        if review is None:
            raise ResourceNotFound("Review")
        if review.status == "removed":
            raise ConflictError("This review was removed by LOCAH's moderators; you can appeal once")
        r, b = ReviewService._clean(rating, body)
        await _as(session, "reviewer")
        kept = [p for p in (await session.execute(select(ReviewPhoto).where(
            ReviewPhoto.review_id == review.id, ReviewPhoto.removed_at.is_(None)))).scalars()]
        drop = {str(x) for x in remove_photo_ids or []}
        for p in kept:
            if str(p.id) in drop:
                p.removed_at = _now()
        pics = ReviewService._photos_in(photos)
        if len([p for p in kept if str(p.id) not in drop]) + len(pics) > MAX_PHOTOS:
            raise _err("photos", "Up to 3 photos")
        for i, (media_type, data) in enumerate(pics):
            session.add(ReviewPhoto(business_id=inv.business_id, review_id=review.id, media_type=media_type,
                                    size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), content=data,
                                    sort_order=10 + i))
        before = review.rating
        review.rating, review.body, review.reviewer_updated_at = r, b, _now()
        review.version += 1
        await session.flush()
        await _as(session, "")
        await ReviewService._after_change(session, review, "review.updated", business=business,
                                          extra={"rating_before": before})
        return await ReviewService.reviewer_view(session, slug, token)

    @staticmethod
    async def decline(session: AsyncSession, slug: str, token: str) -> dict[str, Any]:
        from platform_core.automation import AutomationEngine

        inv, _ = await ReviewService._by_token(session, slug, token)
        if inv.declined_at is None and await ReviewService._review_for(session, inv) is None:
            inv.declined_at = _now()
            await session.flush()
            await AutomationEngine.cancel(session, inv.business_id, ladder_key="review.request", entity_id=inv.id,
                                          reason="The customer said no thanks")
            await ReviewService._answered(session, inv, "declined")
        return await ReviewService.reviewer_view(session, slug, token)

    @staticmethod
    async def appeal(session: AsyncSession, slug: str, token: str, note: str) -> dict[str, Any]:
        """One appeal against a removal (§17.2)."""
        inv, _ = await ReviewService._by_token(session, slug, token)
        review = await ReviewService._review_for(session, inv, lock=True)
        if review is None or review.status != "removed":
            raise ConflictError("Only a removed review can be appealed")
        if review.appeal_status is not None:
            raise ConflictError("A review can be appealed once")
        note = (note or "").strip()
        if not 5 <= len(note) <= 1000:
            raise _err("note", "Say in a few words why the review should be restored")
        await _as(session, "reviewer")
        review.appeal_status, review.appeal_note, review.appealed_at = "open", note, _now()
        await session.flush()
        await _as(session, "")
        session.add(ReviewModerationLog(business_id=review.business_id, review_id=review.id, action="appeal_opened",
                                        note=note))
        await session.flush()
        return await ReviewService.reviewer_view(session, slug, token)

    # ------------------------------------------------------------------ after any change
    @staticmethod
    async def _after_change(session: AsyncSession, review: Review, event: str, *, business: Business | None = None,
                            extra: dict[str, Any] | None = None) -> None:
        from platform_core.automation import AutomationEngine

        await OutboxService.publish(session, event_type=event, business_id=review.business_id, payload={
            "business_id": str(review.business_id), "review_id": str(review.id), "rating": review.rating,
            "status": review.status, "source_type": review.source_type, **(extra or {})})
        if event == "review.published":
            await AutomationEngine.cancel(session, review.business_id, ladder_key="review.request",
                                          entity_id=review.invitation_id, reason="The customer reviewed")
        if event in ("review.published", "review.updated") and review.rating <= 2 and review.status == "published":
            # §17.3 recovery, not deletion: the owner hears at once.
            from platform_core.services.notification import NotificationService

            await NotificationService.fan_out(
                session, business_id=review.business_id, notification_type="reviews.low_rating",
                title=f"{review.reviewer_name} gave {review.rating} star{'s' if review.rating != 1 else ''}",
                body="Reach out and put things right — only they can update their review.",
                required_permission="reviews.reply", severity="warning", resource_type="review",
                resource_id=review.id)

    # ------------------------------------------------------------------ what everyone sees
    @staticmethod
    async def serialize(session: AsyncSession, review: Review, *, public: bool = True,
                        token: str | None = None, slug: str | None = None) -> dict[str, Any]:
        photos = list((await session.execute(select(ReviewPhoto.id).where(
            ReviewPhoto.review_id == review.id, ReviewPhoto.removed_at.is_(None)).order_by(
            ReviewPhoto.sort_order, ReviewPhoto.created_at))).scalars())
        out: dict[str, Any] = {
            "id": str(review.id), "reviewer_name": review.reviewer_name, "rating": review.rating, "body": review.body,
            "verified": SOURCE_WORDS.get(review.source_type, "Verified"),
            "published_at": review.published_at.isoformat() if review.published_at else None,
            "updated_by_reviewer": review.reviewer_updated_at is not None,
            "reply": {"body": review.reply_body, "at": review.reply_at.isoformat() if review.reply_at else None}
            if review.reply_body else None,
            "photos": [str(p) for p in photos], "redacted": review.redacted_at is not None,
        }
        if not public:
            out |= {"status": review.status, "featured": review.featured,
                    "removed": {"reason": review.removed_reason, "reason_words": VIOLATIONS.get(review.removed_reason or ""),
                                "note": review.removed_note,
                                "at": review.removed_at.isoformat() if review.removed_at else None}
                    if review.status == "removed" else None,
                    "appeal": {"status": review.appeal_status, "note": review.appeal_note} if review.appeal_status
                    else None}
        return out

    @staticmethod
    async def summary(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        """§17.2 / §17.5: from every published review — featured or not."""
        rows = (await session.execute(select(Review.rating, func.count()).where(
            Review.business_id == business_id, Review.status == "published").group_by(Review.rating))).all()
        dist = {str(k): 0 for k in range(5, 0, -1)}
        total = n = 0
        for rating, count in rows:
            dist[str(rating)] = int(count)
            total += int(rating) * int(count)
            n += int(count)
        return {"average": _avg(total, n), "count": n, "distribution": dist}

    @staticmethod
    async def public_reviews(session: AsyncSession, business_id: uuid.UUID, *, featured: bool = False,
                             limit: int = 20, offset: int = 0) -> dict[str, Any]:
        q = select(Review).where(Review.business_id == business_id, Review.status == "published")
        if featured:
            q = q.where(Review.featured.is_(True)).order_by(Review.featured_at.desc())
        else:
            q = q.order_by(Review.published_at.desc())
        rows = list((await session.execute(q.limit(min(limit, 50)).offset(max(offset, 0)))).scalars())
        return {**await ReviewService.summary(session, business_id),
                "reviews": [await ReviewService.serialize(session, r) for r in rows]}

    @staticmethod
    async def photo(session: AsyncSession, business_id: uuid.UUID, photo_id: uuid.UUID, *,
                    own_review_id: uuid.UUID | None = None) -> tuple[bytes, str]:
        row = (await session.execute(select(ReviewPhoto, Review.status, Review.id).join(
            Review, Review.id == ReviewPhoto.review_id).where(
            ReviewPhoto.id == photo_id, ReviewPhoto.business_id == business_id,
            ReviewPhoto.removed_at.is_(None)))).first()
        if row is None or (own_review_id is None and row[1] != "published") or (
                own_review_id is not None and row[2] != own_review_id):
            raise ResourceNotFound("Photo")
        return bytes(row[0].content), str(row[0].media_type)

    # ------------------------------------------------------------------ the business
    @staticmethod
    async def get(session: AsyncSession, business_id: uuid.UUID, review_id: uuid.UUID, *,
                  lock: bool = False) -> Review:
        q = select(Review).where(Review.business_id == business_id, Review.id == review_id)
        if lock:
            q = q.with_for_update()
        review = (await session.execute(q.execution_options(populate_existing=True))).scalars().first()
        if review is None:
            raise ResourceNotFound("Review")
        return review

    @staticmethod
    async def business_list(session: AsyncSession, business_id: uuid.UUID, *, view: str = "all",
                            can_see_contact: bool = False) -> dict[str, Any]:
        q = select(Review).where(Review.business_id == business_id)
        if view == "reply":
            q = q.where(Review.status == "published", Review.reply_body.is_(None))
        elif view == "low":
            q = q.where(Review.status == "published", Review.rating <= 2)
        elif view == "featured":
            q = q.where(Review.featured.is_(True), Review.status == "published")
        elif view == "reported":
            q = q.where(Review.id.in_(select(ReviewReport.review_id).where(ReviewReport.business_id == business_id)))
        elif view == "removed":
            q = q.where(Review.status == "removed")
        rows = list((await session.execute(q.order_by(Review.published_at.desc()).limit(300))).scalars())
        reports = {r.review_id: r for r in (await session.execute(select(ReviewReport).where(
            ReviewReport.business_id == business_id).order_by(ReviewReport.created_at))).scalars()}
        contacts = {c.id: c for c in (await session.execute(select(CustomerContact).where(
            CustomerContact.id.in_({r.customer_contact_id for r in rows})))).scalars()} if rows else {}
        labels = {i.id: i.label for i in (await session.execute(select(ReviewInvitation).where(
            ReviewInvitation.id.in_({r.invitation_id for r in rows})))).scalars()} if rows else {}
        out = []
        for r in rows:
            item = await ReviewService.serialize(session, r, public=False)
            rep = reports.get(r.id)
            item["about"] = labels.get(r.invitation_id)
            item["report"] = {"reason": rep.reason, "reason_words": VIOLATIONS[rep.reason], "status": rep.status,
                              "note": rep.note, "decision_note": rep.decision_note} if rep else None
            c = contacts.get(r.customer_contact_id)
            item["customer"] = {"id": str(c.id), "name": c.display_name,
                                "phone": c.phone if can_see_contact else None} if c else None
            out.append(item)
        counts = (await session.execute(select(
            func.count().filter((Review.status == "published") & Review.reply_body.is_(None)),
            func.count().filter((Review.status == "published") & (Review.rating <= 2)),
            func.count().filter(Review.featured.is_(True) & (Review.status == "published")),
        ).where(Review.business_id == business_id))).one()
        return {**await ReviewService.summary(session, business_id), "reviews": out,
                "counts": {"reply": int(counts[0]), "low": int(counts[1]), "featured": int(counts[2])},
                "violations": VIOLATIONS, "max_featured": MAX_FEATURED}

    @staticmethod
    async def reply(session: AsyncSession, business_id: uuid.UUID, review_id: uuid.UUID, actor_id: uuid.UUID,
                    body: str | None) -> Review:
        review = await ReviewService.get(session, business_id, review_id, lock=True)
        if review.status != "published":
            raise ConflictError("This review was removed by LOCAH's moderators")
        text_ = (body or "").strip() or None
        if text_ is not None and len(text_) > 1000:
            raise _err("body", "Keep a reply under 1,000 characters")
        review.reply_body, review.reply_at, review.reply_by = text_, _now() if text_ else None, actor_id if text_ else None
        review.version += 1
        await session.flush()
        await AuditService.record(session, event_type="review.replied", actor_identity_id=actor_id,
                                  actor_context="business", action="reply", business_id=business_id,
                                  resource_type="review", resource_id=review.id, after_state={"reply": text_})
        await ReviewService._after_change(session, review, "review.replied")
        return review

    @staticmethod
    async def feature(session: AsyncSession, business_id: uuid.UUID, review_id: uuid.UUID, actor_id: uuid.UUID,
                      featured: bool) -> Review:
        review = await ReviewService.get(session, business_id, review_id, lock=True)
        if featured and review.status != "published":
            raise ConflictError("Only a published review can be featured")
        if featured and not review.featured:
            n = (await session.execute(select(func.count()).select_from(Review).where(
                Review.business_id == business_id, Review.featured.is_(True),
                Review.status == "published"))).scalar_one()
            if n >= MAX_FEATURED:
                raise ConflictError(f"Your website features up to {MAX_FEATURED} reviews; take one off first")
        review.featured, review.featured_at = featured, _now() if featured else None
        review.version += 1
        await session.flush()
        await AuditService.record(session, event_type="review.featured", actor_identity_id=actor_id,
                                  actor_context="business", action="feature" if featured else "unfeature",
                                  business_id=business_id, resource_type="review", resource_id=review.id,
                                  after_state={"featured": featured})
        await ReviewService._after_change(session, review, "review.featured")
        return review

    @staticmethod
    async def report(session: AsyncSession, business_id: uuid.UUID, review_id: uuid.UUID, actor_id: uuid.UUID,
                     reason: str, note: str | None) -> ReviewReport:
        """§17.2: the business reports with a reason; a LOCAH moderator decides."""
        review = await ReviewService.get(session, business_id, review_id)
        if reason not in VIOLATIONS:
            raise _err("reason", "Choose one of the listed reasons")
        if review.status != "published":
            raise ConflictError("This review is already removed")
        open_ = (await session.execute(select(ReviewReport).where(
            ReviewReport.review_id == review.id, ReviewReport.status == "open"))).scalars().first()
        if open_ is not None:
            raise ConflictError("This review is already with LOCAH's moderators")
        rep = ReviewReport(business_id=business_id, review_id=review.id, reason=reason,
                           note=(note or "").strip()[:500] or None, reported_by=actor_id)
        session.add(rep)
        await session.flush()
        await AuditService.record(session, event_type="review.reported", actor_identity_id=actor_id,
                                  actor_context="business", action="report", business_id=business_id,
                                  resource_type="review", resource_id=review.id,
                                  after_state={"reason": reason, "report_id": str(rep.id)})
        await ReviewService._after_change(session, review, "review.reported", extra={"reason": reason})
        return rep

    @staticmethod
    async def low_open(session: AsyncSession, business_id: uuid.UUID) -> list[Review]:
        """1–2 star reviews from the last 30 days the owner has not answered (Needs you now, §17.3)."""
        return list((await session.execute(select(Review).where(
            Review.business_id == business_id, Review.status == "published", Review.rating <= 2,
            Review.reply_body.is_(None), Review.published_at >= _now() - timedelta(days=30))
            .order_by(Review.published_at.desc()))).scalars())

    # ------------------------------------------------------------------ LOCAH moderators (service session)
    @staticmethod
    async def queue(session: AsyncSession) -> dict[str, Any]:
        reports = list((await session.execute(select(ReviewReport, Review, Business.display_name).join(
            Review, Review.id == ReviewReport.review_id).join(Business, Business.id == Review.business_id).where(
            ReviewReport.status == "open").order_by(ReviewReport.created_at).limit(200))).all())
        appeals = list((await session.execute(select(Review, Business.display_name).join(
            Business, Business.id == Review.business_id).where(Review.appeal_status == "open")
            .order_by(Review.appealed_at).limit(200))).all())
        out_reports = []
        for rep, review, name in reports:
            item = await ReviewService.serialize(session, review, public=False)
            out_reports.append({"report_id": str(rep.id), "business_name": name, "reason": rep.reason,
                                "reason_words": VIOLATIONS[rep.reason], "note": rep.note,
                                "reported_at": rep.created_at.isoformat(), "review": item})
        out_appeals = [{"business_name": name, "review": await ReviewService.serialize(session, r, public=False)}
                       for r, name in appeals]
        return {"reports": out_reports, "appeals": out_appeals, "violations": VIOLATIONS}

    @staticmethod
    async def _mod_get(session: AsyncSession, review_id: uuid.UUID) -> Review:
        review = (await session.execute(select(Review).where(Review.id == review_id).with_for_update()
                                        .execution_options(populate_existing=True))).scalars().first()
        if review is None:
            raise ResourceNotFound("Review")
        return review

    @staticmethod
    async def _log(session: AsyncSession, review: Review, action: str, moderator_id: uuid.UUID,
                   reason: str | None = None, note: str | None = None) -> None:
        session.add(ReviewModerationLog(business_id=review.business_id, review_id=review.id, action=action,
                                        reason=reason, note=note, actor_identity_id=moderator_id))
        await session.flush()
        await AuditService.record(session, event_type=f"review.moderation.{action}", actor_identity_id=moderator_id,
                                  actor_context="admin", action=action, business_id=review.business_id,
                                  resource_type="review", resource_id=review.id,
                                  after_state={"reason": reason, "note": note})

    @staticmethod
    async def dismiss_report(session: AsyncSession, report_id: uuid.UUID, moderator_id: uuid.UUID,
                             note: str | None) -> None:
        rep = (await session.execute(select(ReviewReport).where(ReviewReport.id == report_id)
                                     .with_for_update())).scalars().first()
        if rep is None or rep.status != "open":
            raise ResourceNotFound("Open report")
        rep.status, rep.decided_by, rep.decided_at = "dismissed", moderator_id, _now()
        rep.decision_note = (note or "").strip()[:500] or None
        review = await ReviewService._mod_get(session, rep.review_id)
        await ReviewService._log(session, review, "report_dismissed", moderator_id, rep.reason, rep.decision_note)

    @staticmethod
    async def remove(session: AsyncSession, review_id: uuid.UUID, moderator_id: uuid.UUID, reason: str,
                     note: str | None) -> Review:
        """Only for a listed violation; the reason is logged and the reviewer told (§17.2)."""
        if reason not in VIOLATIONS:
            raise _err("reason", "Choose one of the listed violations")
        review = await ReviewService._mod_get(session, review_id)
        if review.status == "removed":
            raise ConflictError("Already removed")
        await _as(session, "moderator")
        review.status, review.removed_reason, review.removed_at = "removed", reason, _now()
        review.removed_by, review.removed_note = moderator_id, (note or "").strip()[:500] or None
        review.featured, review.featured_at = False, None
        review.version += 1
        await session.flush()
        await _as(session, "")
        for rep in (await session.execute(select(ReviewReport).where(
                ReviewReport.review_id == review.id, ReviewReport.status == "open"))).scalars():
            rep.status, rep.decided_by, rep.decided_at = "upheld", moderator_id, _now()
        await ReviewService._log(session, review, "removed", moderator_id, reason, review.removed_note)
        await ReviewService._tell_reviewer(session, review, "review.removed",
                                           f"Your review was removed: {VIOLATIONS[reason]}. You can appeal once.")
        await ReviewService._after_change(session, review, "review.removed", extra={"reason": reason})
        return review

    @staticmethod
    async def decide_appeal(session: AsyncSession, review_id: uuid.UUID, moderator_id: uuid.UUID, *,
                            restore: bool, note: str | None) -> Review:
        review = await ReviewService._mod_get(session, review_id)
        if review.appeal_status != "open":
            raise ConflictError("No open appeal on this review")
        await _as(session, "moderator")
        review.appeal_status = "upheld" if restore else "rejected"
        review.appeal_decided_at, review.appeal_decided_by = _now(), moderator_id
        if restore:
            review.status, review.removed_reason, review.removed_at, review.removed_by = "published", None, None, None
            review.removed_note = None
        review.version += 1
        await session.flush()
        await _as(session, "")
        await ReviewService._log(session, review, "appeal_upheld" if restore else "appeal_rejected", moderator_id,
                                 note=(note or "").strip()[:500] or None)
        await ReviewService._tell_reviewer(
            session, review, "review.appeal_decided",
            "Your review is back up." if restore else "Your appeal was not upheld; the review stays removed.")
        if restore:
            await ReviewService._after_change(session, review, "review.restored")
        return review

    @staticmethod
    async def redact(session: AsyncSession, review_id: uuid.UUID, moderator_id: uuid.UUID,
                     spans: list[str]) -> Review:
        """A moderator may only take personal data out of the text — nothing else changes (§17.2)."""
        review = await ReviewService._mod_get(session, review_id)
        body = review.body or ""
        spans = [s for s in (x.strip() for x in spans) if s]
        if not spans:
            raise _err("spans", "Select the personal details to remove")
        for s in spans:
            if s not in body:
                raise _err("spans", "Only text that is in the review can be removed")
            body = body.replace(s, REDACTED)
        await _as(session, "moderator")
        review.body, review.redacted_at = body, _now()
        review.version += 1
        await session.flush()
        await _as(session, "")
        await ReviewService._log(session, review, "redacted", moderator_id, "personal_data",
                                 f"{len(spans)} passage{'s' if len(spans) != 1 else ''} removed")
        await ReviewService._after_change(session, review, "review.redacted")
        return review

    @staticmethod
    async def remove_photo(session: AsyncSession, photo_id: uuid.UUID, moderator_id: uuid.UUID) -> None:
        photo = (await session.execute(select(ReviewPhoto).where(ReviewPhoto.id == photo_id)
                                       .with_for_update())).scalars().first()
        if photo is None or photo.removed_at is not None:
            raise ResourceNotFound("Photo")
        await _as(session, "moderator")
        photo.removed_at, photo.removed_by = _now(), moderator_id
        await session.flush()
        await _as(session, "")
        review = await ReviewService._mod_get(session, photo.review_id)
        await ReviewService._log(session, review, "photo_removed", moderator_id, "personal_data")

    @staticmethod
    async def _tell_reviewer(session: AsyncSession, review: Review, activity: str, words: str) -> None:
        """The reviewer is told in My Activity (a LOCAH account) and on their own review link."""
        from platform_core.services.consumer_activity import ConsumerActivityService

        await ConsumerActivityService.record_for_customer_contact(
            session, business_id=review.business_id, customer_contact_id=review.customer_contact_id,
            activity_type=activity, resource_type="review", resource_id=review.id, summary={"message": words})
