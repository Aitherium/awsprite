"""Teach-file parsing tests — pure, no network, no I/O beyond tmp files."""

# isort: skip_file
#
# Same two-config import-order conflict as test_model.py and
# awrelay/tests/test_standalone.py: the repo's ambient ruff knows `awsprite`
# as FIRST-party, the quality gate's `--isolated` run sees it as THIRD-party,
# and no single ordering satisfies both.

from __future__ import annotations

import pytest

from awsprite.model import SpriteError
from awsprite.teach import parse_teach_entries


def test_markdown_sections_become_entries():
    text = "# The ocean\n\nThe ocean covers 70% of Earth.\n\n## Cats\n\nCats sleep a lot.\n"
    entries = parse_teach_entries(text)
    assert [e["title"] for e in entries] == ["The ocean", "Cats"]
    assert entries[0]["kind"] == "fact"
    assert "covers 70%" in entries[0]["content"]
    assert "sleep a lot" in entries[1]["content"]


def test_plain_notes_split_on_blank_lines():
    text = "The ocean\nThe ocean covers 70% of Earth.\n\nCats\nCats sleep a lot.\n"
    entries = parse_teach_entries(text)
    assert [e["title"] for e in entries] == ["The ocean", "Cats"]
    assert entries[0]["content"] == "The ocean covers 70% of Earth."
    assert entries[1]["content"] == "Cats sleep a lot."


def test_single_line_notes_make_one_entry_with_empty_content():
    entries = parse_teach_entries("just one line\n")
    assert len(entries) == 1
    assert entries[0]["title"] == "just one line"
    assert entries[0]["content"] == ""


def test_empty_and_blank_files_produce_no_entries():
    assert parse_teach_entries("") == []
    assert parse_teach_entries("\n\n  \n") == []
    # A bare '#' is not a title — no entries either.
    assert parse_teach_entries("#\n") == []


def test_preheading_content_becomes_its_own_entry():
    text = "Preamble line\n\n## Section One\nbody\n"
    entries = parse_teach_entries(text)
    assert [e["title"] for e in entries] == ["Preamble line", "Section One"]
    assert entries[0]["content"] == ""


def test_titles_and_content_truncate_to_service_limits():
    entries = parse_teach_entries("# " + "t" * 500 + "\n\n" + "c" * 9000 + "\n")
    assert len(entries) == 1
    assert entries[0]["title"] == "t" * 120
    assert entries[0]["content"] == "c" * 4000


def test_crlf_line_endings_are_normalized():
    entries = parse_teach_entries("# Title\r\n\r\nbody line\r\n")
    assert entries[0]["title"] == "Title"
    assert entries[0]["content"] == "body line"


def test_default_kind_applies_to_every_entry():
    entries = parse_teach_entries("# A skill\n", default_kind="skill")
    assert entries[0]["kind"] == "skill"


def test_unknown_kind_raises():
    with pytest.raises(SpriteError, match="kind"):
        parse_teach_entries("# Title\n", default_kind="recipe")
