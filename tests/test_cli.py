"""CLI tests: command wiring, exit codes, honest errors.

The SpriteClient is stubbed via monkeypatch — the network is not the
subject here. Exit-code contract: 0 success, 1 the service refused or was
unreachable, 2 the command could not run at all.
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

import awsprite.cli as cli
from awsprite.client import SpriteError


class _StubClient:
    """Minimal fake with the four surface methods the CLI commands use."""

    def __init__(self, base_url="https://sprite.example"):
        self.base_url = base_url
        self.calls = []

    def status(self):
        self.calls.append(("status",))
        return {
            "id": "x", "name": "Pip", "stage": "child", "form": "scholar",
            "mood_label": "curious", "dormant": False,
            "needs": {"hunger": 0.62, "energy": 0.71, "hygiene": 0.83, "bond": 0.35},
            "mood": {"valence": 0.24, "arousal": 0.53},
            "age_days": 3.25, "knowledge_count": 4,
            "intellect_tier": 2, "intellect_label": "chatterling", "cosmetics": [],
        }

    def talk(self, message):
        self.calls.append(("talk", message))
        return {"reply": "I was just thinking about the ocean.", "sprite": self.status()}

    def teach(self, title, content="", *, kind="fact", private=False):
        self.calls.append(("teach", title, content, kind, private))
        return {"sprite": self.status(), "entry": {"id": "e1", "title": title}}

    def list(self):
        self.calls.append(("list",))
        return [self.status(), dict(self.status(), name="Mochi", stage="teen")]


@pytest.fixture
def stub(monkeypatch):
    client = _StubClient()
    monkeypatch.setattr(cli, "SpriteClient", lambda url, token=None: client)
    return client


def _run(args, monkeypatch):
    monkeypatch.setenv("AWSPRITE_URL", "https://sprite.example")
    return cli.main(args)


def test_cli_status_prints_state(capsys, stub, monkeypatch):
    rc = _run(["status"], monkeypatch)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Pip" in out
    assert "child" in out
    assert "curious" in out
    assert "hunger" in out


def test_cli_status_json(capsys, stub, monkeypatch):
    rc = _run(["--json", "status"], monkeypatch)
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["name"] == "Pip"
    assert data["needs"]["hunger"] == 0.62


def test_cli_talk_prints_the_reply(capsys, stub, monkeypatch):
    rc = _run(["talk", "good morning!"], monkeypatch)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "I was just thinking about the ocean."
    assert stub.calls[0] == ("talk", "good morning!")


def test_cli_teach_teaches_every_entry_from_the_file(capsys, stub, monkeypatch, tmp_path):
    f = tmp_path / "notes.md"
    f.write_text(
        "# The ocean\n\nThe ocean covers 70%.\n\n# Cats\n\nCats sleep.\n", encoding="utf-8"
    )
    rc = _run(["teach", str(f)], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert "taught 2 entries" in out
    assert str(f) in out
    assert [c[1] for c in stub.calls if c[0] == "teach"] == ["The ocean", "Cats"]


def test_cli_teach_missing_file_exits_2(capsys, stub, monkeypatch):
    rc = _run(["teach", "no-such-file.md"], monkeypatch)
    assert rc == 2
    assert "cannot read" in capsys.readouterr().err


def test_cli_teach_empty_file_exits_1_with_an_honest_message(capsys, stub, monkeypatch, tmp_path):
    f = tmp_path / "empty.md"
    f.write_text("", encoding="utf-8")
    rc = _run(["teach", str(f)], monkeypatch)
    assert rc == 1
    err = capsys.readouterr().err
    assert "no teachable entries" in err
    assert str(f) in err


def test_cli_list_prints_companions(capsys, stub, monkeypatch):
    rc = _run(["list"], monkeypatch)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Pip" in out
    assert "Mochi" in out


def test_cli_missing_url_exits_2_and_names_the_env_var(capsys, monkeypatch):
    monkeypatch.delenv("AWSPRITE_URL", raising=False)
    monkeypatch.delenv("AWSPRITE_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        cli.main(["status"])
    assert exc.value.code == 2
    assert "AWSPRITE_URL" in capsys.readouterr().err


def test_cli_unreachable_service_exits_1_naming_the_url(capsys, monkeypatch):
    # SpriteClient construction is I/O-free (the transport runs per call),
    # so the unreachable case surfaces from the request — like a real
    # connection failure, which the CLI must name the URL for.
    class _Down:
        def status(self):
            raise SpriteError(
                "could not reach https://down.example/api/v1/aither-sprite/me/status: refused"
            )

    monkeypatch.setattr(cli, "SpriteClient", lambda url, token=None: _Down())
    rc = cli.main(["--url", "https://down.example", "status"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "https://down.example" in err


def test_cli_teach_failure_mid_batch_names_the_entry(capsys, monkeypatch, tmp_path):
    f = tmp_path / "notes.md"
    f.write_text("# One\n\n# Two\n", encoding="utf-8")

    def failing(url, token=None):
        calls = []

        class C:
            def teach(self, title, content="", *, kind="fact", private=False):
                calls.append(title)
                if title == "Two":
                    raise SpriteError(
                        "POST https://sprite.example/api/v1/aither-sprite/me/teach -> 409: dormant"
                    )
                return {"sprite": {}, "entry": {"id": "e1", "title": title}}

        return C()

    monkeypatch.setattr(cli, "SpriteClient", failing)
    monkeypatch.setenv("AWSPRITE_URL", "https://sprite.example")
    rc = cli.main(["teach", str(f)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "'Two'" in err
    assert "409" in err
