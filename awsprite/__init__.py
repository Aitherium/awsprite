"""awsprite — a portable client for AitherSprite-shaped companion services.

    from awsprite import SpriteClient

    client = SpriteClient("https://sprite.example", token="...")
    state = client.status()
    reply = client.talk("good morning!")["reply"]
    client.teach("The ocean", "covers 70% of Earth")

The companion's state is server-authoritative; this package is a small
standalone client, never the engine. Stdlib-only, no imports from the
monorepo — publishable standalone.
"""

from __future__ import annotations

from awsprite.client import (
    SpriteClient,
    SpriteError,
    SpriteHTTPError,
    build_care_request,
    build_hatch_request,
    build_list_request,
    build_me_request,
    build_revive_request,
    build_status_request,
    build_talk_request,
    build_teach_request,
    build_url,
    build_whisper_request,
)
from awsprite.model import (
    API_PREFIX,
    CARE_ACTIONS,
    KNOWLEDGE_KINDS,
    NEEDS,
    STAGES,
    parse_list_response,
    parse_state,
    parse_talk_response,
    parse_teach_response,
)
from awsprite.teach import parse_teach_entries

__version__ = "0.1.0"

__all__ = [
    "SpriteClient",
    "SpriteError",
    "SpriteHTTPError",
    "parse_state",
    "parse_talk_response",
    "parse_teach_response",
    "parse_list_response",
    "parse_teach_entries",
    "build_url",
    "build_status_request",
    "build_me_request",
    "build_list_request",
    "build_talk_request",
    "build_teach_request",
    "build_hatch_request",
    "build_care_request",
    "build_revive_request",
    "build_whisper_request",
    "API_PREFIX",
    "KNOWLEDGE_KINDS",
    "CARE_ACTIONS",
    "STAGES",
    "NEEDS",
]
