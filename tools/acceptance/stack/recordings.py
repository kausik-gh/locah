"""Write the recordings the acceptance stack replays, from the eval personas.

    uv run python tools/acceptance/stack/recordings.py <out_dir>

replay_ai.json   — the scripted model reading of each persona message, keyed
                   by the owner's exact words (AI_PROVIDER=replay). A message
                   with no recording takes the model-down path.
replay_voice.json — utterances the replay voice "hears" (flows rewrite it).
personas.json    — who says what, for flows.mjs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from platform_testing.interview_personas import ALL_PERSONAS


def main(out: str) -> None:
    root = Path(out)
    root.mkdir(parents=True, exist_ok=True)
    recordings: dict[str, object] = {}
    people: dict[str, object] = {}
    for p in ALL_PERSONAS:
        recordings[p.opening[0]] = p.opening[1]
        recordings.update({text: data for text, data in p.answers.values()})
        people[p.key] = {"name": p.name, "opening": p.opening[0],
                         "answers": {ask: text for ask, (text, _) in p.answers.items()},
                         "category": p.category}
    (root / "replay_ai.json").write_text(json.dumps(recordings, ensure_ascii=False, indent=1), encoding="utf-8")
    (root / "personas.json").write_text(json.dumps(people, ensure_ascii=False, indent=1), encoding="utf-8")
    voice = root / "replay_voice.json"
    if not voice.exists():
        voice.write_text(json.dumps({"utterances": []}), encoding="utf-8")
    print(f"{len(recordings)} recordings, {len(people)} personas -> {root}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "acceptance-out")
