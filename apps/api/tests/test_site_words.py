"""A tenant website's own words in English, Tamil and Hindi (P1-10E6; PR-10,
GP-22 P1 part).

Reads the tenant pages' source (apps/web — read as text, not imported) and the
phrase table they share (apps/web/src/lib/site-words.json): every literal a
tenant page passes to t('…') has Tamil and Hindi wording with the same blanks,
written in its own script; so does every label the API sends that a tenant
page shows (the primary action, the WhatsApp button, sections a module adds,
review badges, payment states, bill and khata kinds, offering kinds, their
buttons, public detail labels and units). The wording itself is LOCAH's first
draft and needs a native speaker's review (VB-22).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app

from platform_core.messaging.words import detect
from platform_testing.phase_b import create_business, new_identity, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "apps" / "web" / "src"
TABLE: dict[str, dict[str, str]] = json.loads((WEB / "lib" / "site-words.json").read_text(encoding="utf-8"))
CALL = re.compile(r"""\bt\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")""")
BLANKS = re.compile(r"\{(\w+)\}")


def _tenant_files() -> list[Path]:
    files = list((WEB / "components" / "website").glob("*.ts*")) + list((WEB / "app" / "[slug]").rglob("*.ts*"))
    return sorted(files)


def _said() -> dict[str, str]:
    found: dict[str, str] = {}
    for f in _tenant_files():
        for m in CALL.finditer(f.read_text(encoding="utf-8")):
            found.setdefault(m.group(1) if m.group(1) is not None else m.group(2), str(f.relative_to(WEB)))
    return found


def _server_labels() -> set[str]:
    from platform_core.catalog.offering_kinds import KINDS
    from platform_core.messaging.entry import JOURNEY_LABELS
    from platform_core.services import invoicing, ledger
    from platform_core.services.payment_collect import LINK_STATE_WORDS, PURPOSES, STATE_WORDS
    from platform_core.services.reviews import SOURCE_WORDS
    from platform_core.website import capabilities as caps

    labels = set(caps.PRIMARY_LABELS.values()) | set(JOURNEY_LABELS.values()) | set(SOURCE_WORDS.values())
    labels |= {"Verified"} | set(PURPOSES.values()) | set(STATE_WORDS.values())
    labels |= {w for w in LINK_STATE_WORDS.values() if w} | set(invoicing.KIND_LABEL.values())
    labels |= set(ledger.KIND_LABEL.values())
    for kind in KINDS.values():
        labels |= {kind.label, kind.cta, *kind.extra_ctas}
        labels |= {f.label for f in kind.fields if f.public} | {f.unit for f in kind.fields if f.public and f.unit}
    for flags, traits in (({"order": True, "join": True, "book": True, "reviews": True, "enquire": True,
                            "request_quote": True, "_kinds": {"class": 1}}, ["quote_led"]),
                          ({"book": True, "enquire": True, "_kinds": {"room_type": 1}}, ["enquiry_led"]),
                          ({"book": True, "_kinds": {}}, [])):
        for section in caps.auto_sections(flags, set(), hidden=[], published_reviews=1, traits=traits):
            labels |= {v for k, v in section["content"].items() if k in ("title", "headline", "cta_label")}
    return labels


def test_every_word_on_a_tenant_page_has_tamil_and_hindi() -> None:
    said = _said()
    assert len(said) > 300, f"the tenant pages go through t() ({len(said)} phrases found)"
    missing = [f"{where}: {text!r}" for text, where in said.items() if text not in TABLE]
    assert missing == [], "tenant phrases without Tamil/Hindi wording:\n" + "\n".join(missing)


def test_every_label_the_api_sends_a_tenant_page_has_its_wording() -> None:
    missing = sorted(label for label in _server_labels() if label not in TABLE)
    assert missing == [], "API labels a tenant page shows, without Tamil/Hindi wording:\n" + "\n".join(missing)


def test_wording_keeps_the_blanks_and_is_written_in_its_script() -> None:
    latin_ok = {"GST", "UPI ID {id}", "WhatsApp"}  # the same in every language
    for text, wording in TABLE.items():
        assert set(wording) == {"ta", "hi"}, f"{text!r} needs exactly ta and hi"
        for lang, words in wording.items():
            assert sorted(BLANKS.findall(words)) == sorted(BLANKS.findall(text)), \
                f"{text!r} [{lang}] fills different blanks: {words!r}"
            assert words.strip(), f"{text!r} [{lang}] is empty"
            if text not in latin_ok:
                assert detect(BLANKS.sub("", words)) == lang, f"{text!r} [{lang}] is not written in its script: {words!r}"


def test_no_locah_colour_is_hard_coded_on_a_tenant_page() -> None:
    """Tenant pages take colour from the business's theme (--site-*), never a fixed hex."""
    hexes = re.compile(r"(?:background|color|border)[^;\n]{0,40}#[0-9a-fA-F]{3,6}\b")
    allowed = {"components/website/WebsitePageView.tsx"}  # the neutral per-personality fallbacks and the preview bar
    found = [f"{f.relative_to(WEB).as_posix()}: {m.group(0)}" for f in _tenant_files() if f.relative_to(WEB).as_posix() not in allowed
             for m in hexes.finditer(f.read_text(encoding="utf-8"))]
    assert found == [], "\n".join(found)


@DB
def test_the_owner_chooses_the_sites_languages_and_the_public_site_reads_them(monkeypatch: Any) -> None:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner)
    base = f"/v1/b/{bid}/website"
    assert client.get(base, headers=owner).json()["data"]["website"]["languages"] == ["en"], "English until chosen"
    bad = client.put(f"{base}/languages", json={"languages": ["en", "fr"]}, headers=owner)
    assert bad.status_code == 422 and "English, Tamil and Hindi" in bad.text
    assert client.put(f"{base}/languages", json={"languages": []}, headers=owner).status_code == 422
    r = client.put(f"{base}/languages", json={"languages": ["ta", "en", "ta"]}, headers=owner)
    assert r.status_code == 200 and r.json()["data"]["languages"] == ["ta", "en"], "Tamil first, no repeats"
    assert client.get(base, headers=owner).json()["data"]["website"]["languages"] == ["ta", "en"]
    [(event,)] = sql("select after_state from platform_audit_events where business_id = :b "
                     "and event_type = 'website.languages.changed'", b=bid)
    assert event == {"languages": ["ta", "en"]}
    _, stranger = new_identity(monkeypatch)
    assert client.put(f"{base}/languages", json={"languages": ["hi"]}, headers=stranger).status_code in (403, 404)
