"""export: the sprite graduates into an adk agent pack. Pure builders, no network."""

import json

import pytest

from awsprite.cli import build_parser, main
from awsprite.client import SpriteClient
from awsprite.export import build_pack, fetch_all_knowledge, slugify, write_pack
from awsprite.model import SpriteError

STATE = {
    "id": "spr_1", "name": "Pip", "stage": "teen", "form": "scholar",
    "needs": {"hunger": 0.4}, "mood": {"valence": 0.2, "arousal": 0.1},
    "mood_label": "curious", "knowledge_count": 3, "age_days": 12.5,
    "intellect": {"tier": 2, "label": "chatty"},
}
ENTRIES = [
    {"id": "k1", "kind": "fact", "title": "The kettle", "content": "Boils at 100 C.",
     "created_at": "2026-09-01T10:00:00Z"},
    {"id": "k2", "kind": "skill", "title": "Make tea", "content": "Kettle, leaves, wait.",
     "created_at": "2026-09-02T10:00:00Z"},
    {"id": "k3", "kind": "fact", "title": "The kettle", "content": "Second page, same title.",
     "created_at": "2026-09-03T10:00:00Z"},
]


def test_pack_has_manifest_identity_index_pages_and_raw_export():
    files = build_pack(STATE, ENTRIES, exported_at="2026-09-21T00:00:00+00:00")
    assert set(files) >= {"agent.yaml", "identity.yaml", "knowledge/INDEX.md",
                          "sprite.json", "README.md"}
    pages = [k for k in files if k.startswith("knowledge/") and k != "knowledge/INDEX.md"]
    assert sorted(pages) == ["knowledge/fact/the-kettle-2.md", "knowledge/fact/the-kettle.md",
                             "knowledge/skill/make-tea.md"]        # collision -> suffixed
    assert "Boils at 100 C." in files["knowledge/fact/the-kettle.md"]
    assert 'sprite_entry_id: "k3"' in files["knowledge/fact/the-kettle-2.md"]
    assert "## fact (2)" in files["knowledge/INDEX.md"]
    assert "## skill (1)" in files["knowledge/INDEX.md"]
    assert "[Make tea](skill/make-tea.md)" in files["knowledge/INDEX.md"]


def test_manifest_and_identity_derive_from_the_sprite():
    files = build_pack(STATE, ENTRIES)
    assert 'name: "Pip"' in files["agent.yaml"]
    assert 'slug: "pip"' in files["agent.yaml"]
    assert 'identity: "pip"' in files["agent.yaml"]
    assert "seed_dir: knowledge" in files["agent.yaml"]
    assert '  stage: "teen"' in files["agent.yaml"]
    assert '  style: "studious"' in files["identity.yaml"]      # scholar form
    raw = json.loads(files["sprite.json"])
    assert raw["state"]["name"] == "Pip" and len(raw["entries"]) == 3


def test_user_strings_are_quoted_so_yaml_cannot_retype_them():
    files = build_pack(dict(STATE, name="yes"), [
        {"id": "k", "kind": "fact", "title": "1.0", "content": "x"}])
    assert 'name: "yes"' in files["agent.yaml"]
    assert 'title: "1.0"' in files["knowledge/fact/1-0.md"]


def test_name_override_and_unknown_kind_fall_back():
    files = build_pack(STATE, [{"id": "k", "kind": "spell", "title": "", "content": "c"}],
                       name="  Nova  ")
    assert 'display_name: "Nova"' in files["identity.yaml"]
    assert "knowledge/fact/untitled.md" in files


def test_non_object_state_is_loud():
    with pytest.raises(SpriteError):
        build_pack(["not", "a", "dict"], [])


def test_slugify():
    assert slugify("The Kettle!") == "the-kettle"
    assert slugify("") == "entry"
    assert len(slugify("x" * 200)) <= 60


def test_fetch_all_knowledge_pages_until_short_page():
    calls = []

    def knowledge(limit, offset):
        calls.append((limit, offset))
        rows = [{"id": str(i)} for i in range(offset, min(offset + limit, 5))]
        return rows, 5
    out = fetch_all_knowledge(knowledge, page=2)
    assert [e["id"] for e in out] == ["0", "1", "2", "3", "4"]
    assert calls == [(2, 0), (2, 2), (2, 4)]


def test_fetch_all_knowledge_stops_on_a_stale_count():
    """A server that keeps reporting count=99 with an empty tail must not loop."""
    def knowledge(limit, offset):
        return ([{"id": "a"}, {"id": "b"}] if offset == 0 else []), 99
    assert len(fetch_all_knowledge(knowledge, page=2)) == 2


def test_write_pack_refuses_a_non_empty_dir_unless_overwrite(tmp_path):
    files = build_pack(STATE, ENTRIES)
    written = write_pack(files, tmp_path / "pip")
    assert len(written) == len(files)
    assert (tmp_path / "pip" / "knowledge" / "skill" / "make-tea.md").read_text(
        encoding="utf-8").startswith("---\n")
    with pytest.raises(SpriteError):
        write_pack(files, tmp_path / "pip")
    write_pack(files, tmp_path / "pip", overwrite=True)


def test_cli_export_end_to_end_through_a_fake_transport(tmp_path, monkeypatch):
    def transport(method, url, body, headers, timeout):
        if url.endswith("/me"):
            return 200, json.dumps(STATE).encode()
        if "/me/knowledge" in url:
            return 200, json.dumps({"entries": ENTRIES, "count": 3}).encode()
        raise AssertionError(url)

    monkeypatch.setattr(
        "awsprite.cli.SpriteClient",
        lambda url, token=None: SpriteClient(url, token=token, transport=transport),
    )
    out = tmp_path / "pip"
    rc = main(["--url", "https://sprite.example", "export", str(out)])
    assert rc == 0
    assert (out / "agent.yaml").exists()
    assert sorted(p.name for p in (out / "knowledge" / "fact").iterdir()) == [
        "the-kettle-2.md", "the-kettle.md"]


def test_parser_has_export():
    ns = build_parser().parse_args(["export", "somewhere", "--name", "Nova", "--overwrite"])
    assert ns.command == "export" and ns.name == "Nova" and ns.overwrite is True
