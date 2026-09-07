"""Pure parsing tests for the sprite-shaped contract — no network anywhere.

The reference shape is the service's public serialization (the "public
dict"): id/name/stage/form/needs/mood/mood_label/dormant/age_days/
cosmetics/knowledge_count/intellect. /me/status serves a lighter subset,
so missing fields must default — but a talk REPLY must never default.
"""

# isort: skip_file
#
# The repo's ambient ruff config knows `awsprite` as FIRST-party and wants it
# in its own block; the quality gate runs ruff `--isolated` (deliberately, so
# the ambient per-file-ignores cannot hide E501/F-rules) where `awsprite`
# reads as THIRD-party and belongs beside pytest. Those two layouts are
# mutually exclusive — one block or two — so no ordering satisfies both and
# this states the conflict instead of flip-flopping the file every time
# whichever gate ran last disagreed. Same fix as awrelay/tests/test_standalone.py.

from __future__ import annotations

import pytest

from awsprite.model import (
    CARE_ACTIONS,
    KNOWLEDGE_KINDS,
    NEEDS,
    SpriteError,
    parse_list_response,
    parse_state,
    parse_talk_response,
    parse_teach_response,
)


def _public_dict(**overrides):
    """The full reference shape — AitherSprite.to_public_dict."""
    base = {
        "id": "a1b2c3",
        "name": "Pip",
        "stage": "child",
        "form": "scholar",
        "needs": {"hunger": 0.62, "energy": 0.71, "hygiene": 0.83, "bond": 0.35},
        "mood": {"valence": 0.241, "arousal": 0.534},
        "mood_label": "curious",
        "dormant": False,
        "age_days": 3.25,
        "cosmetics": [],
        "knowledge_count": 4,
        "intellect": {"tier": 2, "label": "chatterling"},
    }
    base.update(overrides)
    return base


def test_parse_state_reads_the_full_public_dict():
    s = parse_state(_public_dict())
    assert s["id"] == "a1b2c3"
    assert s["name"] == "Pip"
    assert s["stage"] == "child"
    assert s["form"] == "scholar"
    assert s["needs"] == {"hunger": 0.62, "energy": 0.71, "hygiene": 0.83, "bond": 0.35}
    assert s["mood"] == {"valence": 0.241, "arousal": 0.534}
    assert s["mood_label"] == "curious"
    assert s["age_days"] == 3.25
    assert s["knowledge_count"] == 4
    assert s["intellect_tier"] == 2
    assert s["intellect_label"] == "chatterling"
    assert s["cosmetics"] == []


def test_parse_state_tolerates_the_status_subset():
    # /me/status is deliberately lighter than /me — missing fields default
    # rather than raise, so the same parser serves both endpoints.
    s = parse_state({
        "name": "Pip", "stage": "egg", "form": "balanced",
        "needs": {"hunger": 0.9, "energy": 0.9, "hygiene": 0.9, "bond": 0.1},
        "mood": {"valence": -0.4, "arousal": 0.8}, "mood_label": "grumpy",
        "dormant": False, "age_days": 0.1, "knowledge_count": 0,
    })
    assert s["id"] == ""
    assert s["intellect_tier"] == 0
    assert s["intellect_label"] == "pre-verbal"
    assert s["cosmetics"] == []
    assert s["mood_label"] == "grumpy"


def test_parse_state_defaults_missing_needs_and_mood():
    s = parse_state({"name": "Pip", "needs": {"hunger": 0.5}})
    assert s["needs"]["energy"] == 0.0
    assert s["needs"]["bond"] == 0.0
    assert set(s["needs"]) == set(NEEDS)
    assert s["mood"] == {"valence": 0.0, "arousal": 0.0}
    assert s["dormant"] is False


def test_parse_state_rejects_non_object():
    with pytest.raises(SpriteError):
        parse_state(["not", "a", "dict"])
    with pytest.raises(SpriteError):
        parse_state(None)


def test_parse_state_rejects_non_numeric_fields():
    with pytest.raises(SpriteError):
        parse_state({"name": "Pip", "knowledge_count": "lots"})
    with pytest.raises(SpriteError):
        parse_state({"name": "Pip", "needs": {"hunger": "hungry"}})


def test_parse_talk_response_returns_reply_and_sprite():
    data = {"reply": "I was just thinking about the ocean.", "sprite": _public_dict()}
    parsed = parse_talk_response(data)
    assert parsed["reply"] == "I was just thinking about the ocean."
    assert parsed["sprite"]["name"] == "Pip"


def test_parse_talk_response_missing_reply_is_an_error_never_an_empty_string():
    # The honest-failure rule: a talk that returns no reply must not read
    # as "the sprite said nothing".
    with pytest.raises(SpriteError, match="reply"):
        parse_talk_response({"sprite": _public_dict()})
    with pytest.raises(SpriteError, match="reply"):
        parse_talk_response({"reply": None, "sprite": {}})
    with pytest.raises(SpriteError):
        parse_talk_response("just a string")


def test_parse_teach_response_unwraps_entry_and_sprite():
    parsed = parse_teach_response({
        "sprite": _public_dict(),
        "entry": {"id": "e1", "kind": "fact", "title": "The ocean", "content": "..."},
    })
    assert parsed["entry"]["id"] == "e1"
    assert parsed["entry"]["title"] == "The ocean"
    assert parsed["sprite"]["knowledge_count"] == 4


def test_parse_teach_response_requires_an_entry():
    with pytest.raises(SpriteError, match="entry"):
        parse_teach_response({"sprite": _public_dict()})


def test_parse_list_response_accepts_three_shapes():
    sprites = [_public_dict(), _public_dict(name="Mochi", stage="teen")]
    assert [s["name"] for s in parse_list_response({"sprites": sprites})] == ["Pip", "Mochi"]
    assert [s["name"] for s in parse_list_response(sprites)] == ["Pip", "Mochi"]
    # A server that only answers /me reports exactly one companion: yours.
    assert [s["name"] for s in parse_list_response(_public_dict())] == ["Pip"]


def test_parse_list_response_accepts_an_empty_collection():
    assert parse_list_response({"sprites": []}) == []
    assert parse_list_response([]) == []


def test_parse_list_response_rejects_non_sprite_shapes():
    with pytest.raises(SpriteError):
        parse_list_response({"detail": "Not Found"})
    with pytest.raises(SpriteError):
        parse_list_response("nope")


def test_contract_constants_match_the_service_surface():
    assert KNOWLEDGE_KINDS == ("fact", "skill", "link", "lore")
    # teach and talk are care actions on the ENGINE but have their own
    # endpoints; the /me/care Literal is exactly this set.
    assert CARE_ACTIONS == ("feed", "play", "clean", "rest", "pet")
