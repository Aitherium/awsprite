"""The homestead embed: a member's Sprite, living on their own site.

    from awsprite.embed import embed_script, embed_snippet

    js = embed_script()             # the dependency-free sprite-embed.js
    html = embed_snippet("yourname")  # the two lines a homestead pastes

The script is packaged data (``awsprite/web/sprite-embed.js``) and is read
through ``importlib.resources`` so it works from a wheel, a zip or the tree.
It fetches ONE public pet card with ``credentials: 'omit'`` and never touches
cookies: member sites live on ``<name>.aitherium.org``, a separate registrable
domain from the platform, and the embed must never carry a session there.
"""

from __future__ import annotations

import re
from importlib import resources

__all__ = ["DEFAULT_API", "EMBED_FILENAME", "embed_script", "embed_snippet"]

EMBED_FILENAME = "sprite-embed.js"
DEFAULT_API = "https://api.aitherium.com/api/sprite/pet-card/"

# A homestead name is one DNS label: lowercase letters, digits and inner hyphens.
_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def embed_script() -> str:
    """Return the packaged ``sprite-embed.js`` source.

    Returns:
        The JavaScript source as text (UTF-8 decoded).

    Raises:
        FileNotFoundError: if the package was built without its ``web/*.js`` data.
    """
    return resources.files("awsprite").joinpath("web", EMBED_FILENAME).read_text(encoding="utf-8")


def embed_snippet(homestead: str, src: str = f"./{EMBED_FILENAME}") -> str:
    """Return the HTML a homestead page needs to show its Sprite.

    Args:
        homestead: the homestead name (``<name>`` in ``<name>.aitherium.org``).
        src: where the page serves ``sprite-embed.js`` from.

    Returns:
        A slot ``<div>`` plus a deferred ``<script>`` tag.

    Raises:
        ValueError: if ``homestead`` is not a single lowercase DNS label, or ``src``
            contains a quote or angle bracket.
    """
    name = (homestead or "").strip().lower()
    if not _NAME_RE.match(name):
        raise ValueError(f"not a homestead name (one lowercase DNS label): {homestead!r}")
    if any(ch in src for ch in "\"'<>"):
        raise ValueError(f"src must not contain quotes or angle brackets: {src!r}")
    return (
        f'<div data-aither-sprite data-homestead="{name}"></div>\n'
        f'<script src="{src}" defer></script>\n'
    )
