"""Image prompts and the image provider boundary. No live provider network."""

import base64
from typing import Any

import httpx
import pytest

from platform_core.website import image_generation
from platform_core.website.image_generation import (
    family_for_business_type,
    gemini_image_body,
    gemini_image_from,
    generate_image_bytes,
    hero_prompt,
    image_generation_available,
    logo_prompt,
    offering_prompt,
)


def test_restaurant_and_gym_hero_prompts_diverge() -> None:
    food = hero_prompt(
        display_name="Ragi House",
        business_type="restaurant",
        description="Millet kitchen",
    )
    gym = hero_prompt(
        display_name="Iron Hall",
        business_type="gym",
        description="Strength studio",
    )
    assert "spice" in food and "diagonal" in gym
    assert food != gym
    assert "No text" in food


def test_hero_artwork_never_asks_for_the_business_itself() -> None:
    prompt = hero_prompt(
        display_name="Meridian Hospital",
        business_type="clinic",
        description="Our doctors and our 200-bed hospital",
        palette=("#1f3d34", "#c89b3c"),
    )
    lowered = prompt.lower()
    # Name and claims stay out; a model given them draws a building and a sign.
    assert "meridian" not in lowered and "doctors" not in lowered and "200" not in lowered
    assert "photorealistic" not in lowered
    assert "no people" in lowered and "not as a photograph" in lowered
    assert "#1f3d34" in prompt


def test_offering_prompt_is_an_illustration_of_the_item() -> None:
    prompt = offering_prompt(
        display_name="Ragi House",
        business_type="restaurant",
        title="Ragi dosa",
        description="Crisp, served with sambar",
    )
    assert "Ragi dosa" in prompt
    assert "illustration" in prompt and "photorealistic" not in prompt.lower()
    assert family_for_business_type("restaurant") == "food"
    assert family_for_business_type("hotel") == "stay"


def test_logo_is_a_single_letter_monogram() -> None:
    prompt = logo_prompt(initial="teakwood", primary="#6b3e26")
    assert "letter T" in prompt and "#6b3e26" in prompt
    assert "no other letters" in prompt


def test_gemini_request_and_response_shape() -> None:
    body = gemini_image_body("draw", "16:9")
    assert body["generationConfig"] == {
        "responseModalities": ["IMAGE"],
        "imageConfig": {"aspectRatio": "16:9"},
    }
    png = b"\x89PNG fake"
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "here you go"},
                        {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png).decode()}},
                    ]
                }
            }
        ]
    }
    assert gemini_image_from(payload) == ("image/png", png)
    assert gemini_image_from({"candidates": []}) is None


def test_availability_follows_the_configured_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "xai-present")
    # Gemini is the default; an xAI key alone does not switch it on.
    assert image_generation_available() is False
    monkeypatch.setenv("GEMINI_API_KEY", "g-present")
    assert image_generation_available() is True
    monkeypatch.setenv("IMAGE_PROVIDER", "xai")
    assert image_generation_available() is True
    monkeypatch.setenv("IMAGE_PROVIDER", "none")
    assert image_generation_available() is False


class _Recorder:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def client(self, *args, **kwargs):  # noqa: ANN002, ANN003
        recorder = self

        class _Client:
            async def __aenter__(self):  # noqa: ANN204
                return self

            async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
                return False

            async def post(self, url, headers, json):  # noqa: ANN001, ANN201
                recorder.calls.append((url, headers, json))
                return recorder.response

        return _Client()


@pytest.mark.asyncio
async def test_gemini_generation_sends_the_key_in_a_header_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_IMAGE_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "g-secret")
    png = b"\x89PNG bytes"
    recorder = _Recorder(
        httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"inlineData": {"mimeType": "image/png",
                                                            "data": base64.b64encode(png).decode()}}]}}
                ]
            },
        )
    )
    monkeypatch.setattr(image_generation.httpx, "AsyncClient", recorder.client)
    result = await generate_image_bytes("draw", aspect_ratio="1:1")
    assert result is not None and result.bytes == png and result.mime_type == "image/png"
    url, headers, body = recorder.calls[0]
    assert url.endswith("/models/gemini-3.1-flash-image:generateContent")
    assert "g-secret" not in url and headers["x-goog-api-key"] == "g-secret"
    assert body["generationConfig"]["imageConfig"] == {"aspectRatio": "1:1"}


@pytest.mark.asyncio
async def test_a_gemini_failure_does_not_spend_on_the_other_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "g-secret")
    monkeypatch.setenv("XAI_API_KEY", "xai-secret")
    recorder = _Recorder(httpx.Response(429, json={"error": {"message": "quota"}}))
    monkeypatch.setattr(image_generation.httpx, "AsyncClient", recorder.client)
    assert await generate_image_bytes("draw") is None
    assert len(recorder.calls) == 1 and "x.ai" not in recorder.calls[0][0]
