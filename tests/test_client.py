"""Client tests: pure request builders + a swappable transport. No network.

The transport is a constructor argument; every test here either injects a
fake or exercises the real urllib transport against a port nothing listens
on. The honest-failure rule is the load-bearing assertion: every failure
message names the URL it tried.
"""

# isort: skip_file
#
# Same two-config import-order conflict as test_model.py and
# awrelay/tests/test_standalone.py: the repo's ambient ruff knows `awsprite`
# as FIRST-party, the quality gate's `--isolated` run sees it as THIRD-party,
# and no single ordering satisfies both.

from __future__ import annotations

import json

import pytest

from awsprite.client import (
    SpriteClient,
    SpriteError,
    SpriteHTTPError,
    build_care_request,
    build_hatch_request,
    build_list_request,
    build_status_request,
    build_talk_request,
    build_teach_request,
    build_url,
)


def test_build_url_strips_the_trailing_slash():
    assert build_url("https://sprite.example/", "/me/status") == (
        "https://sprite.example/api/v1/aither-sprite/me/status"
    )
    assert build_url("https://sprite.example", "/me") == (
        "https://sprite.example/api/v1/aither-sprite/me"
    )


def test_build_status_request():
    url, method, body = build_status_request("https://sprite.example")
    assert url == "https://sprite.example/api/v1/aither-sprite/me/status"
    assert method == "GET"
    assert body is None


def test_build_list_request_uses_the_collection_root():
    url, method, body = build_list_request("https://sprite.example")
    assert url == "https://sprite.example/api/v1/aither-sprite/"
    assert method == "GET"
    assert body is None


def test_build_talk_request():
    url, method, body = build_talk_request("https://sprite.example", "good morning!")
    assert url == "https://sprite.example/api/v1/aither-sprite/me/talk"
    assert method == "POST"
    assert body == {"message": "good morning!"}


def test_build_talk_request_rejects_blank_lines():
    with pytest.raises(SpriteError, match="non-empty"):
        build_talk_request("https://sprite.example", "   ")


def test_build_teach_request():
    url, method, body = build_teach_request(
        "https://sprite.example", "The ocean", "covers 70% of Earth", kind="lore"
    )
    assert url == "https://sprite.example/api/v1/aither-sprite/me/teach"
    assert body == {
        "kind": "lore", "title": "The ocean", "content": "covers 70% of Earth",
        "private": False,
    }


def test_build_teach_request_truncates_to_service_limits():
    _, _, body = build_teach_request("https://sprite.example", "t" * 500, "c" * 9000)
    assert len(body["title"]) == 120
    assert len(body["content"]) == 4000


def test_build_teach_request_rejects_unknown_kind_and_blank_title():
    with pytest.raises(SpriteError, match="kind"):
        build_teach_request("https://sprite.example", "T", kind="recipe")
    with pytest.raises(SpriteError, match="title"):
        build_teach_request("https://sprite.example", "   ")


def test_build_care_request_rejects_actions_that_have_their_own_endpoints():
    _, _, body = build_care_request("https://sprite.example", "play")
    assert body == {"action": "play"}
    # teach and talk ARE care actions on the engine, but each has its own
    # endpoint — the /me/care surface rejects them.
    with pytest.raises(SpriteError, match="care action"):
        build_care_request("https://sprite.example", "teach")
    with pytest.raises(SpriteError, match="care action"):
        build_care_request("https://sprite.example", "dance")


def test_build_hatch_request_defaults_the_name():
    _, _, body = build_hatch_request("https://sprite.example")
    assert body == {"name": "Sprite"}
    _, _, body2 = build_hatch_request("https://sprite.example", "  ")
    assert body2 == {"name": "Sprite"}


def _fake(status, payload):
    return lambda method, url, body, headers, timeout: (
        status, json.dumps(payload).encode("utf-8")
    )


def test_status_goes_through_the_transport_and_parses():
    seen = {}

    def transport(method, url, body, headers, timeout):
        seen["method"], seen["url"], seen["headers"], seen["body"] = method, url, headers, body
        return 200, json.dumps(
            {"name": "Pip", "stage": "baby", "needs": {"hunger": 0.9}}
        ).encode()

    client = SpriteClient("https://sprite.example", token="tok", transport=transport)
    s = client.status()
    assert s["name"] == "Pip"
    assert s["stage"] == "baby"
    assert seen["method"] == "GET"
    assert seen["url"] == "https://sprite.example/api/v1/aither-sprite/me/status"
    assert seen["headers"]["Authorization"] == "Bearer tok"


def test_talk_posts_the_line_and_parses_the_reply():
    seen = {}

    def transport(method, url, body, headers, timeout):
        seen["body"] = body  # the client passes the body dict through
        return 200, json.dumps({
            "reply": "I was just thinking about the ocean.",
            "sprite": {"name": "Pip", "stage": "child"},
        }).encode()

    client = SpriteClient("https://sprite.example", transport=transport)
    result = client.talk("good morning!")
    assert result["reply"] == "I was just thinking about the ocean."
    assert result["sprite"]["name"] == "Pip"
    assert seen["body"] == {"message": "good morning!"}


def test_teach_posts_the_entry():
    seen = {}

    def transport(method, url, body, headers, timeout):
        seen["body"] = body
        return 200, json.dumps({
            "sprite": {"name": "Pip", "knowledge_count": 1},
            "entry": {"id": "e1", "title": "The ocean"},
        }).encode()

    client = SpriteClient("https://sprite.example", transport=transport)
    result = client.teach("The ocean", "covers 70% of Earth")
    assert result["entry"]["id"] == "e1"
    assert result["sprite"]["knowledge_count"] == 1
    assert seen["body"]["title"] == "The ocean"
    assert seen["body"]["content"] == "covers 70% of Earth"


def test_list_reads_the_collection_root():
    def transport(method, url, body, headers, timeout):
        return 200, json.dumps({"sprites": [{"name": "Pip"}, {"name": "Mochi"}]}).encode()

    client = SpriteClient("https://sprite.example", transport=transport)
    assert [c["name"] for c in client.list()] == ["Pip", "Mochi"]


def test_list_falls_back_to_me_when_the_collection_root_404s():
    urls = []

    def transport(method, url, body, headers, timeout):
        urls.append(url)
        if url.endswith("/api/v1/aither-sprite/"):
            return 404, b'{"detail": "Not Found"}'
        return 200, json.dumps({"name": "Pip", "stage": "egg"}).encode()

    client = SpriteClient("https://sprite.example", transport=transport)
    companions = client.list()
    assert [c["name"] for c in companions] == ["Pip"]
    assert urls == [
        "https://sprite.example/api/v1/aither-sprite/",
        "https://sprite.example/api/v1/aither-sprite/me",
    ]


def test_list_propagates_non_404_root_failures():
    def transport(method, url, body, headers, timeout):
        return 500, b"boom"

    client = SpriteClient("https://sprite.example", transport=transport)
    with pytest.raises(SpriteHTTPError) as exc:
        client.list()
    assert exc.value.status == 500


def test_non_2xx_raises_an_error_naming_url_and_status():
    client = SpriteClient("https://sprite.example", transport=_fake(409, {"detail": "dormant"}))
    with pytest.raises(SpriteError) as exc:
        client.talk("hello?")
    msg = str(exc.value)
    assert "409" in msg
    assert "https://sprite.example/api/v1/aither-sprite/me/talk" in msg


def test_unreachable_transport_error_names_the_url():
    def transport(method, url, body, headers, timeout):
        raise ConnectionRefusedError("refused")

    client = SpriteClient("https://sprite.example", transport=transport)
    with pytest.raises(SpriteError) as exc:
        client.status()
    assert "https://sprite.example/api/v1/aither-sprite/me/status" in str(exc.value)


def test_real_transport_reports_unreachable_localhost():
    # The genuine urllib transport against a port nothing listens on.
    # Anything other than a SpriteError naming the URL is a failure.
    client = SpriteClient("http://127.0.0.1:1", timeout=3)
    with pytest.raises(SpriteError) as exc:
        client.status()
    assert "http://127.0.0.1:1/api/v1/aither-sprite/me/status" in str(exc.value)


def test_malformed_json_body_is_an_error():
    client = SpriteClient("https://sprite.example", transport=lambda *a: (200, b"not json"))
    with pytest.raises(SpriteError, match="non-JSON"):
        client.status()


def test_hatch_care_and_whisper_hit_their_routes():
    seen = []

    def transport(method, url, body, headers, timeout):
        seen.append((method, url, body))
        return 200, json.dumps({"name": "Pip", "stage": "egg"}).encode()

    client = SpriteClient("https://sprite.example", transport=transport)
    client.hatch("Pip")
    client.care("play")
    client.whisper()
    assert seen[0][0] == "POST" and seen[0][1].endswith("/hatch")
    assert seen[0][2] == {"name": "Pip"}
    assert seen[1][0] == "POST" and seen[1][1].endswith("/me/care")
    assert seen[1][2] == {"action": "play"}
    assert seen[2][0] == "GET" and seen[2][1].endswith("/me/whisper")
