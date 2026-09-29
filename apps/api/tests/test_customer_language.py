"""WhatsApp in the customer's language — English, Tamil, Hindi (P1-10E6; PR-10,
GP-22 P1 part; MD §12 "WhatsApp … in the customer's language").

A customer who writes in Tamil or Hindi script is answered in it; anyone can
pick a language from the menu, and that choice sticks. Templates go in the
customer's language when that version is approved. Every phrase the journeys
say has Tamil and Hindi wording with the same blanks. The wording is LOCAH's
own first draft and still needs a native speaker's review (VB-22) — this suite
proves the plumbing, not the prose.
"""

from __future__ import annotations

import ast
import asyncio
import os
import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app

from platform_core.ai_guard import blocked_calls
from platform_core.messaging.words import PHRASES, clock, detect, tr
from platform_testing.phase_b import create_business, new_identity, primary_location, sql

DB = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
client = TestClient(app)
CORE = Path(__file__).resolve().parents[3] / "python" / "core" / "platform_core"


@pytest.fixture(autouse=True)
def _sandbox(monkeypatch: Any) -> None:
    monkeypatch.setenv("MESSAGING_SANDBOX", "1")


class Phone:
    def __init__(self, owner: dict[str, str], bid: str, number: str, name: str) -> None:
        self.owner, self.bid, self.number, self.name = owner, bid, number, name

    def _send(self, **body: Any) -> None:
        r = client.post(f"/v1/platform/businesses/{self.bid}/messaging/sandbox/inbound",
                        json={"from_phone": self.number, "name": self.name, **body}, headers=self.owner)
        assert r.status_code == 200, r.text

    def say(self, text: str) -> None:
        self._send(text=text)

    def tap(self, reply_id: str) -> None:
        offered = self.options()
        assert reply_id in offered, f"{reply_id} not offered: {offered}"
        self._send(button_id=reply_id, button_title=offered[reply_id][:20])

    def last(self, n: int = 1) -> list[str]:
        rows = sql("select m.body from messaging_messages m join messaging_conversations c on c.id = m.conversation_id "
                   "where m.business_id = :b and c.wa_id = :w and m.direction = 'out' order by m.created_at desc, "
                   "m.id desc limit :n", b=self.bid, w=self.number, n=n)
        return [str(r[0]) for r in reversed(rows)]

    def options(self) -> dict[str, str]:
        rows = sql("select m.payload from messaging_messages m join messaging_conversations c "
                   "on c.id = m.conversation_id where m.business_id = :b and c.wa_id = :w and m.direction = 'out' "
                   "and m.kind = 'interactive' order by m.created_at desc limit 1", b=self.bid, w=self.number)
        return {o["id"]: o["title"] for o in (rows[0][0]["options"] if rows else [])}

    def language(self) -> tuple[Any, Any]:
        [(lang, source)] = sql("select c.language, c.language_source from customer_relationships_contacts c "
                               "join messaging_conversations m on m.contact_id = c.id "
                               "where m.business_id = :b and m.wa_id = :w", b=self.bid, w=self.number)
        return lang, source


def _shop(monkeypatch: Any) -> tuple[dict[str, str], str]:
    _, owner = new_identity(monkeypatch)
    bid = create_business(client, owner, business_type="retail", name="Anbu Stores", modules=(
        "offerings-catalog", "orders", "fulfilment", "payments", "customer-relationships", "messaging"))
    ch = client.post(f"/v1/platform/businesses/{bid}/messaging/channel/sandbox",
                     json={"display_phone": "+919840022222", "display_name": "Anbu Stores"}, headers=owner)
    assert ch.status_code == 200, ch.text
    primary_location(client, owner, bid)
    r = client.post(f"/v1/platform/businesses/{bid}/products", json={
        "status": "active", "offering_type": "product", "title": "Ghee 500 ml", "price_amount": 320,
        "visibility": "public"}, headers=owner)
    assert r.status_code == 200, r.text
    return owner, bid


# ---------------------------------------------------------------- every phrase has its wording
def _said(path: Path) -> list[tuple[int, str]]:
    """Every literal passed to tr(lang, "…") or ctx.tr("…") in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # tr's own definition passes its argument on, and _status passes STATUS_WORDS (checked below);
    # everything else must pass a literal.
    wrapper = {n.lineno for d in ast.walk(tree) if isinstance(d, ast.FunctionDef) and d.name in ("tr", "_status")
               for n in ast.walk(d) if isinstance(n, ast.Call)}
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or node.lineno in wrapper:
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == "tr" and len(node.args) >= 2:
            arg = node.args[1]
        elif isinstance(fn, ast.Attribute) and fn.attr == "tr" and node.args:
            arg = node.args[0]
        else:
            continue
        texts = _literals(arg)
        assert texts, f"{path.name}:{node.lineno} passes a non-literal to tr — its wording can't be checked"
        found.extend((node.lineno, t) for t in texts)
    return found


def _literals(arg: ast.expr) -> list[str]:
    """The phrase, or both phrases of `"a" if x else "b"`; empty when it is not written out."""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return [arg.value]
    if isinstance(arg, ast.IfExp):
        body, orelse = _literals(arg.body), _literals(arg.orelse)
        return body + orelse if body and orelse else []
    return []


def test_every_phrase_the_journeys_say_has_tamil_and_hindi_with_the_same_blanks() -> None:
    from platform_core.messaging.journeys import STATUS_WORDS

    blanks = re.compile(r"\{(\w+)\}")
    said = [(p.name, line, text) for p in (CORE / "messaging" / "journeys.py", CORE / "services" / "messaging.py")
            for line, text in _said(p)] + [("journeys.py", 0, words) for words in STATUS_WORDS.values()]
    assert len(said) > 150, f"the journeys go through tr ({len(said)} phrases found)"
    missing = [f"{name}:{line} {text!r}" for name, line, text in said if text not in PHRASES]
    assert missing == [], "phrases without Tamil/Hindi wording:\n" + "\n".join(missing)
    for text, wording in PHRASES.items():
        assert set(wording) == {"ta", "hi"}, f"{text!r} needs exactly ta and hi"
        want = sorted(blanks.findall(text))
        for lang, words in wording.items():
            assert sorted(blanks.findall(words)) == want, f"{text!r} [{lang}] fills different blanks: {words!r}"
            assert detect(words) == lang or not re.search(r"[^\W\d_]", blanks.sub("", words)), \
                f"{text!r} [{lang}] is not written in its script: {words!r}"
    used = {text for _, _, text in said}
    assert sorted(set(PHRASES) - used) == [], "wording nobody says"


def test_script_detection_days_and_times() -> None:
    from datetime import date, time

    assert detect("வணக்கம்") == "ta" and detect("नमस्ते") == "hi" and detect("hello") is None
    assert detect("ok 2") is None and detect("அ") is None, "one stray letter is not a language"
    assert tr("ta", "Total {amount}", amount="₹990") == "மொத்தம் ₹990"
    assert tr("en", "Total {amount}", amount="₹990") == "Total ₹990"
    assert tr("hi", "not a phrase") == "not a phrase", "anything without wording stays in English"
    assert clock(time(17, 30), "en") == "5:30 pm" and clock(time(17, 30), "ta") == "மாலை 5:30"
    assert clock(time(9, 0), "hi") == "सुबह 9" and clock(time(9, 0), "en") == "9 am"
    from platform_core.messaging.words import day_words

    assert day_words(date(2026, 9, 29), "en") == "Tue 29 Sep"
    assert day_words(date(2026, 9, 29), "ta").startswith("செவ்வாய்")


# ---------------------------------------------------------------- a Tamil customer, start to finish
@DB
def test_a_customer_who_writes_in_tamil_orders_in_tamil(monkeypatch: Any) -> None:
    owner, bid = _shop(monkeypatch)
    phone = Phone(owner, bid, "919876522221", "Selvi")
    phone.say("வணக்கம்")
    assert phone.language() == ("ta", "detected")
    menu_row = sql("select m.body, m.payload from messaging_messages m where m.business_id = :b and "
                   "m.kind = 'interactive' order by m.created_at desc limit 1", b=bid)[0]
    assert menu_row[0] == tr("ta", "Hi {name}! This is {business}. What would you like to do?", name="Selvi",
                             business="Anbu Stores")
    titles = {o["id"]: o["title"] for o in menu_row[1]["options"]}
    assert titles["m:order"] == "ஆர்டர் செய்ய" and titles["talk_to_person"] == "ஒருவரிடம் பேச"
    assert titles["m:lang"].startswith("Language · மொழி"), "the language row reads in every language"

    phone.tap("m:order")
    [item] = [k for k in phone.options() if k.startswith("o:item:")]
    phone.tap(item)
    assert set(phone.options()) >= {"o:qty:1", "o:qty:2"}
    phone.tap("o:qty:2")
    assert phone.last()[0].startswith("சேர்க்கப்பட்டது. உங்கள் கூடை: 2 பொருட்கள்")
    phone.tap("o:checkout")
    summary = phone.last()[0]
    assert "மொத்தம் ₹640.00" in summary and "வாங்கும்போது பணம்" in summary, summary
    phone.tap("o:place")
    [(number, channel)] = sql("select order_number, channel from orders_orders where business_id = :b", b=bid)
    assert channel == "whatsapp"
    placed = tr("ta", "Order {number} placed for {amount}. {business} will confirm it here. Follow it: {link}",
                number=number, amount="₹640.00", business="Anbu Stores", link="")
    assert any(m.startswith(placed) and "/track/" in m and m.endswith("lang=ta") for m in phone.last(3)), \
        "the tracking link opens in Tamil too"

    # Asking for a person, and STOP, are answered in Tamil too.
    phone.say("ஆளிடம் பேச வேண்டும்")
    assert phone.last()[0] == tr("ta", "Thanks — someone from {business} will reply here soon.", business="Anbu Stores")
    other = Phone(owner, bid, "919876522222", "Rani")
    other.say("நிறுத்து")
    assert other.last()[0].startswith("இனி WhatsApp-இல் எங்கள் சலுகைகள் வராது")
    assert blocked_calls() == []


# ---------------------------------------------------------------- choosing Hindi from the menu
@DB
def test_a_customer_chooses_hindi_and_it_sticks(monkeypatch: Any) -> None:
    owner, bid = _shop(monkeypatch)
    phone = Phone(owner, bid, "919876533331", "Asha")
    phone.say("hi")
    assert phone.language() == (None, None), "English letters say nothing about language"
    assert phone.last()[0].startswith("Hi Asha! This is Anbu Stores."), "English by default"
    phone.tap("m:lang")
    assert set(phone.options()) == {"l:en", "l:ta", "l:hi"}
    phone.tap("l:hi")
    assert phone.language() == ("hi", "chosen")
    done, menu = phone.last(2)
    assert done == tr("hi", "Done — we'll write to you in English.") and "हिंदी" in done, done
    assert menu == tr("hi", "Hi {name}! This is {business}. What would you like to do?", name="Asha",
                      business="Anbu Stores")
    phone.say("வணக்கம்")  # writing Tamil later does not undo a choice
    assert phone.language() == ("hi", "chosen") and detect(phone.last()[0]) == "hi"
    phone.say("menu")
    assert phone.options()["m:order"] == "ऑर्डर करें"
    phone.tap("m:lang")
    phone.tap("l:en")
    assert phone.language() == ("en", "chosen") and phone.last(2)[0] == "Done — we'll write to you in English."
    assert blocked_calls() == []


# ---------------------------------------------------------------- templates in the customer's language
@DB
def test_templates_go_in_the_customers_language_when_approved(monkeypatch: Any) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from platform_core.services.messaging import MessagingService
    from platform_testing.phase_b import db_url

    owner, bid = _shop(monkeypatch)
    base = f"/v1/platform/businesses/{bid}"
    tamil = client.post(f"{base}/customers", json={"display_name": "Kala", "phone": "+919876544441"},
                        headers=owner).json()["data"]
    plain = client.post(f"{base}/customers", json={"display_name": "John", "phone": "+919876544442"},
                        headers=owner).json()["data"]
    sql("update customer_relationships_contacts set language = 'ta', language_source = 'chosen' where id = :c",
        c=tamil["id"])

    async def confirm(contact: dict[str, Any], key: str) -> tuple[str, str, str]:
        engine = create_async_engine(db_url(), poolclass=NullPool)
        try:
            async with AsyncSession(engine) as s, s.begin():
                msg = await MessagingService.send_template(
                    s, uuid.UUID(bid), to=contact["phone"], key="order_confirmed",
                    params=["ORD-1", "Anbu Stores", "₹640"], contact_id=uuid.UUID(contact["id"]), idempotency_key=key)
                return str(msg.language), str(msg.status), str(msg.body)
        finally:
            await engine.dispose()

    lang, status, body = asyncio.run(confirm(tamil, "t1"))
    assert (lang, status) == ("ta", "sent") and body.startswith("உங்கள் ஆர்டர் ORD-1"), body
    assert asyncio.run(confirm(plain, "p1"))[0] == "en", "no language → the business's (English)"
    # Only the English version approved: a Tamil customer still gets the message, in English.
    sql("update messaging_templates set status = 'rejected' where business_id = :b and template_key = 'order_confirmed' "
        "and language = 'ta'", b=bid)
    assert asyncio.run(confirm(tamil, "t2"))[0] == "en"
    # The business writes in Hindi: a customer with no language gets Hindi.
    assert client.put(f"{base}/messaging/settings", json={"language": "hi"}, headers=owner).status_code == 200
    assert asyncio.run(confirm(plain, "p2"))[0] == "hi"
