"""Business-scoped Documents workflows on the existing rendered-PDF foundation.

Private customer uploads are bounded database objects, not public media assets.
Tokens are random bearer credentials stored only as SHA-256 digests and bound to
one request or one expiring file download. No source-domain tables are read.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import PurePath
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.context_resolver import bind_public_context
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.services.outbox import OutboxService

FIELD_TYPES = frozenset({"text", "textarea", "number", "date", "select", "checkbox",
                         "radio", "file", "signature", "consent"})
TEMPLATE_KINDS = frozenset({"agreement", "consent", "intake", "certificate", "report", "generic"})
RELATED_TYPES = frozenset({"customer", "quote", "project", "job", "booking", "membership",
                           "academic_student", "order", "supplier", "general"})
FILE_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png", "image/webp"})
MAX_FILE_BYTES = 5 * 1024 * 1024
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    payload = value if isinstance(value, bytes) else _json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _view(row: Any) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, uuid.UUID) else
            value.isoformat() if isinstance(value, datetime) else value
            for key, value in dict(row).items()}


def _ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def validate_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not 1 <= len(fields) <= 30:
        raise ValidationError("A form needs 1–30 fields")
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for position, raw in enumerate(fields):
        key = str(raw.get("key", "")).strip()
        kind = str(raw.get("type", "")).strip()
        label = str(raw.get("label", "")).strip()
        if not KEY_PATTERN.fullmatch(key) or key in seen or kind not in FIELD_TYPES or not 1 <= len(label) <= 120:
            raise ValidationError(f"Invalid form field at position {position + 1}")
        seen.add(key)
        options = raw.get("options") or []
        if kind in {"select", "radio"}:
            if not isinstance(options, list) or not 2 <= len(options) <= 30 or any(
                not isinstance(option, str) or not 1 <= len(option.strip()) <= 80 for option in options
            ) or len(set(options)) != len(options):
                raise ValidationError(f"{key} needs distinct choices")
        elif options:
            raise ValidationError(f"{key} cannot have choices")
        help_text = str(raw.get("help_text") or "").strip()
        if len(help_text) > 300:
            raise ValidationError(f"{key} help text is too long")
        result.append({"key": key, "type": kind, "label": label,
                       "required": bool(raw.get("required", False)), "help_text": help_text,
                       "options": options if kind in {"select", "radio"} else [], "order": position})
    if sum(field["type"] == "signature" for field in result) > 1:
        raise ValidationError("Only one signature field is supported")
    return result


async def _event(session: AsyncSession, *, business_id: uuid.UUID, request_id: uuid.UUID | None,
                 kind: str, actor_id: uuid.UUID | None, signer: str | None = None,
                 ip: str | None = None, user_agent: str | None = None,
                 details: dict[str, Any] | None = None, correlation_id: str | None = None) -> None:
    await session.execute(text("""INSERT INTO document_activity
        (business_id,request_id,event_type,actor_kind,actor_identity_id,signer_name,
         request_ip,request_user_agent,details)
        VALUES (:bid,:rid,:kind,:actor_kind,:actor,:signer,:ip,:ua,CAST(:details AS jsonb))"""),
        {"bid": business_id, "rid": request_id, "kind": kind,
         "actor_kind": "merchant" if actor_id else "request_link", "actor": actor_id,
         "signer": signer, "ip": _ip(ip), "ua": (user_agent or "")[:500],
         "details": _json(details or {})})
    await OutboxService.publish(session, event_type=kind, business_id=business_id,
        correlation_id=correlation_id,
        payload={"request_id": str(request_id) if request_id else None,
                 "actor_kind": "merchant" if actor_id else "request_link", **(details or {})})


class DocumentWorkflows:
    @staticmethod
    async def create_template(session: AsyncSession, *, business_id: uuid.UUID,
                              kind: str, title: str, description: str,
                              traits: dict[str, Any], content: dict[str, Any],
                              actor_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        if kind not in TEMPLATE_KINDS or not title.strip() or not isinstance(content, dict):
            raise ValidationError("Invalid document template")
        if len(_json(content)) > 20000 or len(_json(traits)) > 2000:
            raise ValidationError("Template content is too large")
        row = (await session.execute(text("""INSERT INTO document_templates
            (business_id,kind,title,description,traits,content,created_by)
            VALUES (:bid,:kind,:title,:description,CAST(:traits AS jsonb),CAST(:content AS jsonb),:actor)
            RETURNING id,business_id,kind,title,description,traits,content,version,created_at"""),
            {"bid": business_id, "kind": kind, "title": title.strip(),
             "description": description.strip()[:1000], "traits": _json(traits),
             "content": _json(content), "actor": actor_id})).mappings().one()
        await _event(session, business_id=business_id, request_id=None, kind="document.created",
                     actor_id=actor_id, details={"template_id": str(row["id"])},
                     correlation_id=correlation_id)
        return _view(row)

    @staticmethod
    async def list_templates(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await session.execute(text("""SELECT id,kind,title,description,traits,version,created_at
            FROM document_templates WHERE business_id=:bid ORDER BY created_at DESC LIMIT 100"""),
            {"bid": business_id})).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def create_form(session: AsyncSession, *, business_id: uuid.UUID, title: str,
                          kind: str, fields: list[dict[str, Any]], consent_text: str | None,
                          guardian_required: bool, actor_id: uuid.UUID,
                          correlation_id: str) -> dict[str, Any]:
        if kind not in TEMPLATE_KINDS - {"certificate"} or not 1 <= len(title.strip()) <= 160:
            raise ValidationError("Invalid form")
        validated = validate_fields(fields)
        if consent_text and len(consent_text) > 5000:
            raise ValidationError("Consent text is too long")
        form = (await session.execute(text("""INSERT INTO document_forms
            (business_id,title,kind,created_by) VALUES (:bid,:title,:kind,:actor) RETURNING id"""),
            {"bid": business_id, "title": title.strip(), "kind": kind,
             "actor": actor_id})).scalar_one()
        version = await DocumentWorkflows._insert_version(session, business_id, form, 1,
            validated, consent_text, guardian_required, actor_id)
        await _event(session, business_id=business_id, request_id=None, kind="document.created",
                     actor_id=actor_id, details={"form_id": str(form), "version": 1},
                     correlation_id=correlation_id)
        return {"id": str(form), "title": title.strip(), "kind": kind,
                "current_version": 1, "version": version}

    @staticmethod
    async def _insert_version(session: AsyncSession, business_id: uuid.UUID, form_id: uuid.UUID,
                              version: int, fields: list[dict[str, Any]], consent_text: str | None,
                              guardian_required: bool, actor_id: uuid.UUID) -> dict[str, Any]:
        definition = {"fields": fields, "consent_text": consent_text or "",
                      "guardian_required": guardian_required}
        row = (await session.execute(text("""INSERT INTO document_form_versions
            (business_id,form_id,version,fields,consent_text,guardian_required,definition_sha256,created_by)
            VALUES (:bid,:fid,:version,CAST(:fields AS jsonb),:consent,:guardian,:hash,:actor)
            RETURNING id,form_id,version,fields,consent_text,guardian_required,definition_sha256,created_at"""),
            {"bid": business_id, "fid": form_id, "version": version,
             "fields": _json(fields), "consent": consent_text,
             "guardian": guardian_required, "hash": _hash(definition),
             "actor": actor_id})).mappings().one()
        return _view(row)

    @staticmethod
    async def version_form(session: AsyncSession, *, business_id: uuid.UUID, form_id: uuid.UUID,
                           fields: list[dict[str, Any]], consent_text: str | None,
                           guardian_required: bool, actor_id: uuid.UUID,
                           correlation_id: str) -> dict[str, Any]:
        validated = validate_fields(fields)
        row = (await session.execute(text("""SELECT current_version FROM document_forms
            WHERE business_id=:bid AND id=:fid FOR UPDATE"""),
            {"bid": business_id, "fid": form_id})).first()
        if row is None:
            raise ResourceNotFound("Form")
        next_version = row[0] + 1
        version = await DocumentWorkflows._insert_version(session, business_id, form_id,
            next_version, validated, consent_text, guardian_required, actor_id)
        await session.execute(text("""UPDATE document_forms SET current_version=:version,
            updated_at=clock_timestamp() WHERE business_id=:bid AND id=:fid"""),
            {"version": next_version, "bid": business_id, "fid": form_id})
        await _event(session, business_id=business_id, request_id=None, kind="document.created",
                     actor_id=actor_id, details={"form_id": str(form_id), "version": next_version},
                     correlation_id=correlation_id)
        return version

    @staticmethod
    async def list_forms(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await session.execute(text("""SELECT f.id,f.title,f.kind,f.current_version,
            v.id AS version_id,v.fields,v.consent_text,v.guardian_required,v.created_at
            FROM document_forms f
            JOIN document_form_versions v ON v.business_id=f.business_id AND v.form_id=f.id
              AND v.version=f.current_version WHERE f.business_id=:bid
            ORDER BY f.created_at DESC LIMIT 100"""), {"bid": business_id})).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def create_request(session: AsyncSession, *, business_id: uuid.UUID,
                             request_type: str, title: str, form_id: uuid.UUID | None,
                             related_type: str, related_id: uuid.UUID | None,
                             customer_contact_id: uuid.UUID | None, days_valid: int,
                             actor_id: uuid.UUID, correlation_id: str) -> dict[str, Any]:
        if request_type not in {"form", "upload"} or not 1 <= len(title.strip()) <= 160:
            raise ValidationError("Invalid document request")
        if related_type not in RELATED_TYPES or (related_type != "general" and related_id is None):
            raise ValidationError("Invalid related resource")
        if not 1 <= days_valid <= 30 or (request_type == "form") != (form_id is not None):
            raise ValidationError("Invalid request duration or form")
        version_id = None
        if form_id:
            version_id = (await session.execute(text("""SELECT v.id FROM document_forms f
                JOIN document_form_versions v ON v.business_id=f.business_id AND v.form_id=f.id
                  AND v.version=f.current_version WHERE f.business_id=:bid AND f.id=:fid"""),
                {"bid": business_id, "fid": form_id})).scalar_one_or_none()
            if version_id is None:
                raise ResourceNotFound("Form")
        if customer_contact_id:
            found = (await session.execute(text("""SELECT id FROM customer_relationships_contacts
                WHERE business_id=:bid AND id=:cid AND deleted_at IS NULL"""),
                {"bid": business_id, "cid": customer_contact_id})).scalar_one_or_none()
            if found is None:
                raise ResourceNotFound("Customer")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=days_valid)
        row = (await session.execute(text("""INSERT INTO document_requests
            (business_id,request_type,title,form_version_id,related_type,related_id,
             customer_contact_id,token_hash,expires_at,requested_by)
            VALUES (:bid,:type,:title,:version,:related,:related_id,:contact,:hash,:expires,:actor)
            RETURNING id,request_type,title,related_type,related_id,status,expires_at,created_at"""),
            {"bid": business_id, "type": request_type, "title": title.strip(),
             "version": version_id, "related": related_type, "related_id": related_id,
             "contact": customer_contact_id, "hash": _hash(token),
             "expires": expires, "actor": actor_id})).mappings().one()
        await _event(session, business_id=business_id, request_id=row["id"],
                     kind="document.requested", actor_id=actor_id,
                     details={"request_type": request_type}, correlation_id=correlation_id)
        slug = (await session.execute(text("SELECT slug FROM businesses WHERE id=:bid"),
                {"bid": business_id})).scalar_one()
        return {**_view(row), "token": token,
                "public_path": f"/document-request/{slug}/{token}"}

    @staticmethod
    async def list_requests(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await session.execute(text("""SELECT r.id,r.request_type,r.title,r.related_type,
            r.related_id,r.status,r.expires_at,r.created_at,r.fulfilled_at,
            s.id AS submission_id,f.id AS file_id
            FROM document_requests r LEFT JOIN document_submissions s ON s.request_id=r.id
            LEFT JOIN document_files f ON f.request_id=r.id AND f.field_key='requested_file'
            WHERE r.business_id=:bid ORDER BY r.created_at DESC LIMIT 100"""),
            {"bid": business_id})).mappings().all()
        return [_view(row) for row in rows]

    @staticmethod
    async def _public(session: AsyncSession, slug: str, token: str,
                      *, lock: bool = False) -> tuple[uuid.UUID, dict[str, Any]]:
        if not 32 <= len(token) <= 96:
            raise ResourceNotFound("Document request")
        digest = _hash(token)
        if lock:
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:hash), 4721)"),
                                  {"hash": digest})
        business_id = (await session.execute(text("SELECT document_request_business(:hash)"),
                      {"hash": digest})).scalar_one_or_none()
        if business_id is None:
            raise ResourceNotFound("Document request")
        await bind_public_context(session, business_id)
        await session.execute(text("SELECT set_config('app.document_request_token_hash',:hash,true)"),
                              {"hash": digest})
        business_slug = (await session.execute(text("SELECT slug FROM businesses WHERE id=:bid"),
                       {"bid": business_id})).scalar_one_or_none()
        if business_slug != slug:
            raise ResourceNotFound("Document request")
        query = """SELECT id,request_type,title,form_version_id,related_type,related_id,
            customer_contact_id,status,expires_at,created_at FROM document_requests
            WHERE business_id=:bid AND token_hash=:hash"""
        request = (await session.execute(text(query),
                   {"bid": business_id, "hash": digest})).mappings().one_or_none()
        if request is None:
            raise ResourceNotFound("Document request")
        return business_id, dict(request)

    @staticmethod
    async def public_view(session: AsyncSession, slug: str, token: str) -> dict[str, Any]:
        business_id, request = await DocumentWorkflows._public(session, slug, token)
        # The customer should see whose request this is even when the business
        # has no published website to frame the page.
        business_name = (await session.execute(text("SELECT display_name FROM businesses WHERE id=:bid"),
                         {"bid": business_id})).scalar_one_or_none()
        result = {"id": str(request["id"]), "title": request["title"],
                  "request_type": request["request_type"], "status": request["status"],
                  "expires_at": request["expires_at"].isoformat(), "business_name": business_name}
        if request["request_type"] == "form" and request["status"] == "open":
            version = (await session.execute(text("""SELECT id,version,fields,
                consent_text,guardian_required FROM document_form_versions
                WHERE business_id=:bid AND id=:vid"""),
                {"bid": business_id, "vid": request["form_version_id"]})).mappings().one()
            result["form"] = _view(version)
        return result

    @staticmethod
    async def _version(session: AsyncSession, business_id: uuid.UUID,
                       version_id: uuid.UUID) -> dict[str, Any]:
        row = (await session.execute(text("""SELECT id,version,fields,consent_text,
            guardian_required,definition_sha256 FROM document_form_versions
            WHERE business_id=:bid AND id=:vid"""),
            {"bid": business_id, "vid": version_id})).mappings().one_or_none()
        if row is None:
            raise ResourceNotFound("Form version")
        return dict(row)

    @staticmethod
    async def _validate_answers(session: AsyncSession, business_id: uuid.UUID,
                                request_id: uuid.UUID, fields: list[dict[str, Any]],
                                answers: dict[str, Any], signature: dict[str, Any] | None) -> None:
        known = {field["key"] for field in fields if field["type"] != "signature"}
        if set(answers) - known:
            raise ValidationError("Unknown form answer")
        for field in fields:
            key, kind = field["key"], field["type"]
            if kind == "signature":
                if field["required"] and signature is None:
                    raise ValidationError(f"{field['label']} is required")
                continue
            value = answers.get(key)
            if value is None or value == "":
                if field["required"]:
                    raise ValidationError(f"{field['label']} is required")
                continue
            if kind in {"text", "textarea"}:
                if not isinstance(value, str) or len(value.strip()) > (4000 if kind == "textarea" else 500):
                    raise ValidationError(f"Invalid answer for {key}")
            elif kind == "number":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValidationError(f"Invalid number for {key}")
            elif kind == "date":
                try:
                    date.fromisoformat(value)
                except (TypeError, ValueError):
                    raise ValidationError(f"Invalid date for {key}") from None
            elif kind in {"select", "radio"}:
                if value not in field["options"]:
                    raise ValidationError(f"Invalid choice for {key}")
            elif kind in {"checkbox", "consent"}:
                if not isinstance(value, bool) or (kind == "consent" and field["required"] and not value):
                    raise ValidationError(f"Invalid confirmation for {key}")
            elif kind == "file":
                try:
                    file_id = uuid.UUID(str(value))
                except ValueError:
                    raise ValidationError(f"Invalid file for {key}") from None
                found = (await session.execute(text("""SELECT id FROM document_files
                    WHERE business_id=:bid AND request_id=:rid AND field_key=:key AND id=:fid"""),
                    {"bid": business_id, "rid": request_id, "key": key,
                     "fid": file_id})).scalar_one_or_none()
                if found is None:
                    raise ValidationError(f"File for {key} was not uploaded")

    @staticmethod
    def _signature(signature: dict[str, Any] | None, signer_name: str) -> dict[str, Any] | None:
        if signature is None:
            return None
        kind, value = signature.get("kind"), signature.get("value")
        if kind == "typed":
            if not isinstance(value, str) or value.strip().casefold() != signer_name.strip().casefold():
                raise ValidationError("Typed signature must match the signer name")
            return {"kind": "typed", "value": value.strip()}
        if kind == "drawn":
            if not isinstance(value, list) or not 1 <= len(value) <= 30:
                raise ValidationError("A drawn signature needs strokes")
            count = 0
            for stroke in value:
                if not isinstance(stroke, list) or not 2 <= len(stroke) <= 500:
                    raise ValidationError("Invalid signature stroke")
                for point in stroke:
                    if (not isinstance(point, list) or len(point) != 2 or
                            any(isinstance(n, bool) or not isinstance(n, (int, float))
                                or not math.isfinite(n) or not 0 <= n <= 1 for n in point)):
                        raise ValidationError("Invalid signature point")
                    count += 1
            if count > 5000:
                raise ValidationError("Signature is too detailed")
            return {"kind": "drawn", "value": value}
        raise ValidationError("Choose a typed or drawn signature")

    @staticmethod
    async def submit(session: AsyncSession, *, slug: str, token: str,
                     answers: dict[str, Any], signer_name: str,
                     signature: dict[str, Any] | None, age_confirmed: bool,
                     guardian_relationship: str | None, ip: str | None,
                     user_agent: str | None) -> dict[str, Any]:
        business_id, request = await DocumentWorkflows._public(session, slug, token, lock=True)
        if request["request_type"] != "form":
            raise ValidationError("This link requests a file, not a form")
        if request["status"] != "open":
            raise ConflictError("This form has already been submitted")
        name = signer_name.strip()
        if not 1 <= len(name) <= 160 or len(_json(answers)) > 30000:
            raise ValidationError("Invalid form answers or signer name")
        version = await DocumentWorkflows._version(session, business_id, request["form_version_id"])
        signed = DocumentWorkflows._signature(signature, name)
        await DocumentWorkflows._validate_answers(session, business_id, request["id"],
                                                   version["fields"], answers, signed)
        relation = (guardian_relationship or "").strip()
        if version["guardian_required"] and (not age_confirmed or not 1 <= len(relation) <= 120):
            raise ValidationError("Age confirmation and guardian relationship are required")
        if len(relation) > 120:
            raise ValidationError("Guardian relationship is too long")
        snapshot = {"form_version_id": str(version["id"]),
                    "definition_sha256": version["definition_sha256"],
                    "answers": answers, "signer_name": name,
                    "age_confirmed": age_confirmed, "guardian_relationship": relation,
                    "signature": signed}
        digest = _hash(snapshot)
        row = (await session.execute(text("""INSERT INTO document_submissions
            (business_id,request_id,form_version_id,answers,signer_name,
             declared_guardian_relationship,age_confirmed,content_sha256,request_ip,request_user_agent)
            VALUES (:bid,:rid,:vid,CAST(:answers AS jsonb),:signer,:relation,:age,:hash,:ip,:ua)
            RETURNING id,form_version_id,content_sha256,submitted_at"""),
            {"bid": business_id, "rid": request["id"], "vid": version["id"],
             "answers": _json(answers), "signer": name, "relation": relation or None,
             "age": age_confirmed, "hash": digest, "ip": _ip(ip),
             "ua": (user_agent or "")[:500]})).mappings().one()
        if signed:
            await session.execute(text("""INSERT INTO document_signatures
                (business_id,submission_id,kind,value,signer_name,signer_contact_id,
                 content_sha256,request_ip,request_user_agent)
                VALUES (:bid,:sid,:kind,CAST(:value AS jsonb),:signer,:contact,:hash,:ip,:ua)"""),
                {"bid": business_id, "sid": row["id"], "kind": signed["kind"],
                 "value": _json(signed["value"]), "signer": name,
                 "contact": request["customer_contact_id"], "hash": digest,
                 "ip": _ip(ip), "ua": (user_agent or "")[:500]})
        await _event(session, business_id=business_id, request_id=request["id"],
                     kind="form.submitted", actor_id=None, signer=name, ip=ip,
                     user_agent=user_agent, details={"submission_id": str(row["id"]),
                                                 "form_version_id": str(version["id"])})
        if signed:
            await _event(session, business_id=business_id, request_id=request["id"],
                         kind="document.signed", actor_id=None, signer=name, ip=ip,
                         user_agent=user_agent, details={"submission_id": str(row["id"]),
                                                     "content_sha256": digest})
        await session.execute(text("""UPDATE document_requests
            SET status='fulfilled',fulfilled_at=clock_timestamp()
            WHERE id=:rid AND business_id=:bid"""),
            {"rid": request["id"], "bid": business_id})
        return _view(row)

    @staticmethod
    async def upload(session: AsyncSession, *, slug: str, token: str,
                     field_key: str, filename: str, content_type: str, content: bytes,
                     ip: str | None, user_agent: str | None) -> dict[str, Any]:
        business_id, request = await DocumentWorkflows._public(session, slug, token, lock=True)
        if request["status"] != "open":
            raise ConflictError("This request is already complete")
        if not KEY_PATTERN.fullmatch(field_key):
            raise ValidationError("Invalid file field")
        if request["request_type"] == "upload":
            if field_key != "requested_file":
                raise ValidationError("This link accepts only its requested file")
        else:
            version = await DocumentWorkflows._version(session, business_id, request["form_version_id"])
            if not any(f["key"] == field_key and f["type"] == "file" for f in version["fields"]):
                raise ValidationError("This form has no such file field")
        if content_type not in FILE_TYPES or not 1 <= len(content) <= MAX_FILE_BYTES:
            raise ValidationError("Upload a PDF or JPEG/PNG/WebP under 5 MB")
        if not ((content_type == "application/pdf" and content.startswith(b"%PDF-")) or
                (content_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or
                (content_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")) or
                (content_type == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP")):
            raise ValidationError("File content does not match its type")
        clean_name = PurePath(filename.replace("\\", "/")).name.strip()[:160]
        if not clean_name or "\x00" in clean_name:
            raise ValidationError("Invalid filename")
        existing = (await session.execute(text("""SELECT id,sha256 FROM document_files
            WHERE business_id=:bid AND request_id=:rid AND field_key=:key"""),
            {"bid": business_id, "rid": request["id"], "key": field_key})).first()
        digest = _hash(content)
        if existing:
            if existing[1] != digest:
                raise ConflictError("This file field is already filled")
            return {"id": str(existing[0]), "sha256": digest, "created": False}
        row = (await session.execute(text("""INSERT INTO document_files
            (business_id,request_id,field_key,related_type,related_id,filename,
             content_type,size_bytes,sha256,content)
            VALUES (:bid,:rid,:key,:related,:related_id,:name,:mime,:size,:hash,:content)
            RETURNING id,field_key,filename,content_type,size_bytes,sha256,created_at"""),
            {"bid": business_id, "rid": request["id"], "key": field_key,
             "related": request["related_type"], "related_id": request["related_id"],
             "name": clean_name, "mime": content_type, "size": len(content),
             "hash": digest, "content": content})).mappings().one()
        await _event(session, business_id=business_id, request_id=request["id"],
                     kind="document.uploaded", actor_id=None, ip=ip, user_agent=user_agent,
                     details={"file_id": str(row["id"]), "sha256": digest})
        if request["request_type"] == "upload":
            await session.execute(text("""UPDATE document_requests
                SET status='fulfilled',fulfilled_at=clock_timestamp()
                WHERE id=:rid AND business_id=:bid"""),
                {"rid": request["id"], "bid": business_id})
        return _view(row)

    @staticmethod
    async def submission(session: AsyncSession, business_id: uuid.UUID,
                         submission_id: uuid.UUID) -> dict[str, Any]:
        row = (await session.execute(text("""SELECT s.id,s.request_id,s.form_version_id,
            s.answers,s.signer_name,s.declared_guardian_relationship,s.age_confirmed,
            s.content_sha256,s.submitted_at,s.request_ip,s.request_user_agent,
            v.version AS form_version,v.definition_sha256,
            g.kind AS signature_kind,g.value AS signature_value,g.signed_at
            FROM document_submissions s JOIN document_form_versions v ON v.id=s.form_version_id
            LEFT JOIN document_signatures g ON g.submission_id=s.id
            WHERE s.business_id=:bid AND s.id=:sid"""),
            {"bid": business_id, "sid": submission_id})).mappings().one_or_none()
        if row is None:
            raise ResourceNotFound("Submission")
        return _view(row)

    @staticmethod
    async def create_access_link(session: AsyncSession, *, business_id: uuid.UUID,
                                 file_id: uuid.UUID, actor_id: uuid.UUID) -> dict[str, Any]:
        found = (await session.execute(text("""SELECT id FROM document_files
            WHERE business_id=:bid AND id=:fid"""),
            {"bid": business_id, "fid": file_id})).scalar_one_or_none()
        if found is None:
            raise ResourceNotFound("File")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(minutes=5)
        await session.execute(text("""INSERT INTO document_access_links
            (business_id,file_id,token_hash,expires_at,created_by)
            VALUES (:bid,:fid,:hash,:expires,:actor)"""),
            {"bid": business_id, "fid": file_id, "hash": _hash(token),
             "expires": expires, "actor": actor_id})
        return {"token": token, "expires_at": expires.isoformat(), "file_id": str(file_id)}

    @staticmethod
    async def download(session: AsyncSession, token: str) -> tuple[bytes, dict[str, Any]]:
        if not 32 <= len(token) <= 96:
            raise ResourceNotFound("File link")
        digest = _hash(token)
        business_id = (await session.execute(text("SELECT document_access_business(:hash)"),
                       {"hash": digest})).scalar_one_or_none()
        if business_id is None:
            raise ResourceNotFound("File link")
        await bind_public_context(session, business_id)
        await session.execute(text("SELECT set_config('app.document_access_token_hash',:hash,true)"),
                              {"hash": digest})
        row = (await session.execute(text("""SELECT f.content,f.filename,f.content_type,f.sha256
            FROM document_access_links l JOIN document_files f ON f.id=l.file_id
            WHERE l.business_id=:bid AND l.token_hash=:hash AND l.expires_at>clock_timestamp()"""),
            {"bid": business_id, "hash": digest})).first()
        if row is None:
            raise ResourceNotFound("File link")
        return bytes(row[0]), {"filename": row[1], "content_type": row[2], "sha256": row[3]}
