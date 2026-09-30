"""The acceptance API with STAND-IN pictures — to click through the editor's
picture buttons in a real browser without Gemini. Test-only, local only.

    ACCEPT_STANDIN_IMAGES=1 tools/acceptance/stack/api.sh   (see api.sh)

Gemini's bytes become a labelled plate (owner_flow_v4.plate) and Storage a
local folder served on :8899. Everything else — the editor's endpoints, the
policy, provenance, approve / remove — is the product's own. Never evidence
that Gemini works: that is gemini_verify_v4.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

if "@localhost:" not in os.getenv("DATABASE_URL", "") and "@127.0.0.1:" not in os.getenv("DATABASE_URL", ""):
    sys.exit("local databases only")
sys.path.insert(0, str(Path(__file__).parent))
os.environ["IMAGE_PROVIDER"] = "gemini"

import uvicorn  # noqa: E402

import platform_core.interview.media_director as md  # noqa: E402
import platform_core.media.supabase_storage as storage  # noqa: E402
import platform_core.services.website_images as website_images  # noqa: E402
import platform_core.website.image_generation as images  # noqa: E402
from owner_flow_v4 import plate  # noqa: E402

MEDIA = Path(os.getenv("LOCAH_V4_MEDIA_DIR", "acceptance-out/standin-media")).resolve()
URL = os.getenv("LOCAH_V4_MEDIA_URL", "http://localhost:8899")


async def _draw(prompt: str, *, aspect_ratio: str = "16:9", **_: Any) -> Any:
    return images.GeneratedImage(mime_type="image/jpeg", bytes=plate(prompt, aspect_ratio), model="STAND-IN",
                                 latency_ms=1, prompt=prompt), ""


async def _draw_bytes(prompt: str, aspect_ratio: str = "16:9", **_: Any) -> Any:
    return (await _draw(prompt, aspect_ratio=aspect_ratio))[0]


async def _put(*, storage_key: str, body: bytes, **_: Any) -> None:
    path = MEDIA / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


images.image_generation_available = lambda: True
md.generate_image = _draw
website_images.generate_image_bytes = _draw_bytes
storage.put_generated_object = _put
storage.public_url = lambda bucket, key: f"{URL}/{key}"

from platform_api.main import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("API_PORT", "8010")))
