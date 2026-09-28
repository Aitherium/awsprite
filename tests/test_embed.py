"""The homestead embed: packaged, cookie-free, and identical to the template's copy."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from awsprite.embed import DEFAULT_API, EMBED_FILENAME, embed_script, embed_snippet

PKG_FILE = Path(__file__).resolve().parent.parent / "awsprite" / "web" / EMBED_FILENAME
# packages/awsprite/tests -> parents[3] is AitherOS/ in the monorepo. When awsprite
# is published standalone there is no AitherOS/ tree at all, and only then is the
# byte-identity check skipped; a monorepo checkout with the template dir but no
# copy of the script is a FAILURE, not a skip.
_AITHEROS = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = _AITHEROS / "templates" / "homestead-template"


def test_script_loads_from_package_data():
    js = embed_script()
    assert js.strip(), "embed script is empty"
    assert "data-aither-sprite" in js
    assert js == PKG_FILE.read_text(encoding="utf-8")


def test_script_omits_credentials_and_never_touches_cookies():
    js = embed_script()
    assert "credentials: 'omit'" in js
    assert "document.cookie" not in js
    assert not re.search(r"\bcookie\s*=", js, re.I)
    assert "include'" not in js  # never credentials: 'include'
    assert "innerHTML" not in js  # server data is rendered with textContent only


def test_script_defaults_and_overrides():
    js = embed_script()
    assert DEFAULT_API in js
    assert "data-api" in js
    assert "data-homestead" in js
    assert ".aitherium.org" in js
    assert "aitherium.com'" not in js.replace(DEFAULT_API, "")
    assert "prefers-reduced-motion" in js


def test_script_is_ascii_and_lf():
    raw = PKG_FILE.read_bytes()
    raw.decode("ascii")
    assert b"\r" not in raw


def test_snippet_shape():
    html = embed_snippet("Meadow")
    assert 'data-homestead="meadow"' in html
    assert f'src="./{EMBED_FILENAME}"' in html
    assert "defer" in html


@pytest.mark.parametrize("bad", ["", "-x", "x-", "a.b", "a b", "a\"b", "x" * 64, "<script>"])
def test_snippet_refuses_non_label_names(bad):
    with pytest.raises(ValueError):
        embed_snippet(bad)


def test_snippet_refuses_quoted_src():
    with pytest.raises(ValueError):
        embed_snippet("meadow", src='x" onload="y')


def test_template_copy_is_byte_identical():
    if not (_AITHEROS / "templates").is_dir():
        pytest.skip("standalone awsprite checkout: no AitherOS/templates tree")
    copy = TEMPLATE_DIR / EMBED_FILENAME
    assert copy.is_file(), f"template is missing its copy of the embed: {copy}"
    assert copy.read_bytes() == PKG_FILE.read_bytes(), (
        f"{copy} drifted from {PKG_FILE}; copy the package file over it"
    )
