"""Recorded model answers for tests and acceptance runs (Capability Universe §27).

`AI_PROVIDER=replay` with `LOCAH_AI_REPLAY_FILE=<path>` serves structured
answers from a JSON file instead of a model: for the interview, keyed by the
owner's exact message; nothing is ever sent anywhere. A message with no
recording fails like an unreachable model, so the deterministic path takes
over — exactly what happens in production when the provider is down.

Never set in staging or production: it answers only what was recorded.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReplayProvider:
    provider_name = "replay"

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self.last_usage: dict[str, Any] | None = None
        loaded = json.loads(self._path.read_text(encoding="utf-8"))
        self._recordings: dict[str, dict[str, Any]] = {
            str(k): v for k, v in (loaded.items() if isinstance(loaded, dict) else [])
        }

    @property
    def model_name(self) -> str:
        return "replay"

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        if model_config.get("purpose") == "business.interview":
            try:
                message = str(json.loads(prompt).get("message", ""))
            except (ValueError, AttributeError):
                message = ""
            recorded = self._recordings.get(message)
            if recorded is not None:
                self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "model": "replay"}
                return dict(recorded)
        raise LookupError("no recording for this request")
