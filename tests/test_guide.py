# isort: skip_file
"""Spirit guide + training surface of the awsprite client and CLI. No network."""
from __future__ import annotations

import json

import pytest

from awsprite.client import (
    SpriteClient,
    SpriteError,
    build_challenge_request,
    build_guide_answer_request,
    build_guide_beat_request,
    build_guide_request,
    build_train_request,
)
from awsprite import cli

BASE = "https://sprite.example"
PFX = BASE + "/api/v1/aither-sprite"
VIEW = {"temperament": "bright", "available_acts": [], "offer": None,
        "stats": {"strength": 3, "dexterity": 1, "speed": 0}, "stat_cap": 25,
        "ladder": {"rung": 2, "of": 10, "next_foe": "Grumble Toad", "wins": 1, "losses": 0},
        "charms": [], "equipped": []}


def test_builders():
    assert build_guide_request(BASE) == (PFX + "/me/guide", "GET", None)
    assert build_guide_beat_request(BASE) == (PFX + "/me/guide/beat", "POST", {"act": None})
    assert build_guide_beat_request(BASE, "spar")[2] == {"act": "spar"}
    assert build_guide_answer_request(BASE, True) == (PFX + "/me/guide/answer", "POST",
                                                       {"accept": True})
    assert build_train_request(BASE, "speed") == (PFX + "/me/train", "POST", {"stat": "speed"})
    assert build_challenge_request(BASE) == (PFX + "/me/challenge", "POST", None)


def test_train_rejects_an_unknown_stat_before_any_request():
    with pytest.raises(SpriteError):
        build_train_request(BASE, "charisma")


def test_client_posts_through_the_transport():
    seen = []

    def transport(method, url, body, headers, timeout):
        seen.append((method, url, body))
        return 200, json.dumps({**VIEW, "result": {"stat": "speed", "gain": 1,
                                                   "value": 1, "cap": 25}}).encode()

    out = SpriteClient(BASE, transport=transport).train("speed")
    assert seen == [("POST", PFX + "/me/train", {"stat": "speed"})]
    assert out["result"]["value"] == 1


def test_cli_challenge_prints_the_fight(monkeypatch, capsys):
    def fake_client(_args):
        return SpriteClient(BASE, transport=lambda *a: (200, json.dumps(
            {**VIEW, "result": {"foe": "Grumble Toad", "rung": 2, "won": False,
                                "rounds": 9, "charm": "ember"}}).encode()))

    monkeypatch.setattr(cli, "_client_from_args", fake_client)
    assert cli.main(["--url", BASE, "challenge"]) == 0
    out = capsys.readouterr().out
    assert "lost to Grumble Toad, found a ember charm" in out
    assert "ladder rung 2/10" in out


def test_cli_answer_only_accepts_yes_or_no():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["answer", "maybe"])
