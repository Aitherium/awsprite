"""The sprite-shaped contract: shapes, parsing, errors. No network, no I/O.

The reference shape is the live Genesis router's serialization
(``AitherSprite.to_public_dict``): id/name/stage/form/needs/mood/
mood_label/dormant/age_days/cosmetics/knowledge_count/intellect. A
sprite-shaped server may serve a SUBSET — the ``/me/status`` poll target is
deliberately lighter than ``/me`` — so missing fields default rather than
raise.

What never defaults: a REPLY. A talk that returns no reply is an error, not
an empty string: the honest-failure rule. A silent empty answer reads as
"the sprite said nothing" while a dead server reads as a dead server; this
client's whole point is that those two must never be confused.
"""

from __future__ import annotations

from typing import Any, Dict, List

#: The REST prefix every sprite-shaped server speaks.
API_PREFIX = "/api/v1/aither-sprite"

#: Knowledge kinds the teach surface accepts (router Literal).
KNOWLEDGE_KINDS = ("fact", "skill", "link", "lore")

#: Care actions the /me/care surface accepts. teach and talk ARE care
#: actions on the engine, but each has its own endpoint — this is the
#: router's Literal, which is the contract this client speaks.
CARE_ACTIONS = ("feed", "play", "clean", "rest", "pet")

STAGES = ("egg", "baby", "child", "teen", "adult", "elder")

NEEDS = ("hunger", "energy", "hygiene", "bond")

#: Service-side field limits the client mirrors when building requests
#: (the engine's MAX_KNOWLEDGE_TITLE / MAX_KNOWLEDGE_CONTENT and the talk
#: route's max_length).
MAX_TITLE = 120
MAX_CONTENT = 4000
MAX_MESSAGE = 2000


class SpriteError(Exception):
    """The sprite-shaped server refused, was unreachable, or answered with
    a shape this client cannot read. Raised, never swallowed into an empty
    result — see the module docstrings for the honest-failure rule."""


class SpriteHTTPError(SpriteError):
    """The server ANSWERED with a non-2xx status. Carries the URL and
    status so a caller can distinguish "no such route" (404) from a real
    refusal."""

    def __init__(self, method: str, url: str, status: int, detail: str) -> None:
        super().__init__(f"{method} {url} -> {status}: {detail}")
        self.method = method
        self.url = url
        self.status = status
        self.detail = detail


def parse_state(data: Any) -> Dict[str, Any]:
    """Normalize any sprite-shaped state dict into the client's view.

    Tolerates the /me/status subset and any missing field (safe defaults);
    rejects a non-object outright so a shape error is loud, not silent.
    """
    if not isinstance(data, dict):
        raise SpriteError(f"sprite state was not an object: {data!r}")
    raw_needs = data.get("needs") or {}
    raw_mood = data.get("mood") or {}
    intellect = data.get("intellect") or {}
    try:
        needs: Dict[str, float] = {
            n: float(raw_needs.get(n, 0.0) or 0.0) for n in NEEDS
        }
        mood: Dict[str, float] = {
            "valence": float(raw_mood.get("valence", 0.0) or 0.0),
            "arousal": float(raw_mood.get("arousal", 0.0) or 0.0),
        }
        knowledge_count = int(data.get("knowledge_count", 0) or 0)
        age_days = float(data.get("age_days", 0.0) or 0.0)
        tier = int(intellect.get("tier", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise SpriteError(f"sprite state carried non-numeric fields: {exc}") from exc
    return {
        "id": str(data.get("id", "")),
        "name": str(data.get("name", "Sprite")),
        "stage": str(data.get("stage", "egg")),
        "form": str(data.get("form", "balanced")),
        "needs": needs,
        "mood": mood,
        "mood_label": str(data.get("mood_label", "curious")),
        "dormant": bool(data.get("dormant", False)),
        "age_days": age_days,
        "knowledge_count": knowledge_count,
        "intellect_tier": tier,
        "intellect_label": str(intellect.get("label", "pre-verbal")),
        "cosmetics": list(data.get("cosmetics") or []),
    }


def parse_talk_response(data: Any) -> Dict[str, Any]:
    """``{'reply': str, 'sprite': {...}}`` — the talk contract.

    A reply is REQUIRED. A talk response with no reply is an error, never
    an empty string: the one thing worse than a dead server is a server
    that looks fine and says nothing.
    """
    if not isinstance(data, dict):
        raise SpriteError(f"talk response was not an object: {data!r}")
    reply = data.get("reply")
    if reply is None:
        raise SpriteError("talk response carried no 'reply' field")
    return {"reply": str(reply), "sprite": parse_state(data.get("sprite") or {})}


def parse_teach_response(data: Any) -> Dict[str, Any]:
    """``{'sprite': {...}, 'entry': {...}}`` — the teach contract."""
    if not isinstance(data, dict):
        raise SpriteError(f"teach response was not an object: {data!r}")
    entry = data.get("entry")
    if not isinstance(entry, dict):
        raise SpriteError("teach response carried no 'entry' object")
    return {"sprite": parse_state(data.get("sprite") or {}), "entry": entry}


def parse_list_response(data: Any) -> List[Dict[str, Any]]:
    """Companions from any sprite-shaped server. Tolerated shapes:
    ``{'sprites': [...]}`` (collection root), a bare JSON array, or a
    single companion dict (a server that only answers /me). Anything else
    is an error, never an empty list.
    """
    if isinstance(data, list):
        return [parse_state(d) for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        sprites = data.get("sprites")
        if isinstance(sprites, list):
            return [parse_state(d) for d in sprites if isinstance(d, dict)]
        if "name" in data or "stage" in data:
            return [parse_state(data)]
    raise SpriteError(f"list response was not a sprite collection: {data!r}")
