"""SpriteClient — a thin, portable client for an AitherSprite-shaped server.

Talks to the REST surface any sprite-shaped companion service exposes
(Genesis's router is the reference; prefix ``/api/v1/aither-sprite``):

    GET  /api/v1/aither-sprite/me/status   needs/mood/evolution state
    POST /api/v1/aither-sprite/me/talk     send a line, get the reply
    POST /api/v1/aither-sprite/me/teach    feed the companion a knowledge entry
    GET  /api/v1/aither-sprite/            collection root ({"sprites": [...]})

plus hatch/care/revive/whisper/knowledge for the rest of the v1 read/write
surface. Auth is an optional Bearer token — the same identity path a hosted
companion uses. This client never carries an internal-service key: that
credential is fleet-only and this package ships publicly.

Stdlib-only: the one network call is ``urllib.request.urlopen``, swappable
in tests via the ``transport=`` constructor arg. Request builders and
response parsers are module-level pure functions (``build_*_request`` here,
``awsprite.model.parse_*``) so the whole contract is unit-testable with no
network and no mock HTTP stack.

Standalone by design: when the server is unreachable, every method raises
``SpriteError`` naming the exact URL it tried. There is no offline fallback
and no silent empty reply — a companion client with nothing to talk to is
not a degraded companion client, it is not a companion client.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from awsprite.model import (
    API_PREFIX,
    CARE_ACTIONS,
    KNOWLEDGE_KINDS,
    MAX_CONTENT,
    MAX_MESSAGE,
    MAX_TITLE,
    SpriteError,
    SpriteHTTPError,
    parse_list_response,
    parse_state,
    parse_talk_response,
    parse_teach_response,
)

#: transport(method, url, body, headers, timeout) -> (status, body_bytes)
Transport = Callable[[str, str, Optional[dict], dict, float], Tuple[int, bytes]]


# --------------------------------------------------------------------------- #
# The one place the network happens
# --------------------------------------------------------------------------- #


def _urllib_transport(
    method: str, url: str, body: Optional[dict], headers: dict, timeout: float
) -> Tuple[int, bytes]:
    """The default transport: ``urllib`` and nothing else.

    A server that ANSWERS with 4xx/5xx is a reachable server — its status
    and body come back so the caller's error names both the URL and the
    server's own message. A server that cannot be reached at all raises
    ``SpriteError`` naming the URL.
    """
    req = urllib.request.Request(url, method=method, headers=headers)
    if body is not None:
        req.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        # 4xx/5xx: the server answered. Hand its message back to the caller.
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise SpriteError(f"could not reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SpriteError(f"timed out after {timeout}s reaching {url}") from exc


# --------------------------------------------------------------------------- #
# Pure request builders — given a URL, produce the request. No network.
# --------------------------------------------------------------------------- #


def build_url(base_url: str, path: str) -> str:
    """Compose a sprite-shaped URL: ``{base}/api/v1/aither-sprite{path}``.

    ``base_url`` is the origin (scheme + host, optionally a port); a
    trailing slash is tolerated. If ``base_url`` already ends in the
    prefix, it is NOT re-appended — pass the origin, not a route.
    """
    return base_url.rstrip("/") + API_PREFIX + path


def build_status_request(base_url: str) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) for the companion's current state."""
    return (build_url(base_url, "/me/status"), "GET", None)


def build_me_request(base_url: str) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) for the full /me state (the /me/status superset)."""
    return (build_url(base_url, "/me"), "GET", None)


def build_list_request(base_url: str) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) for the collection root — every known companion."""
    return (build_url(base_url, "/"), "GET", None)


def build_talk_request(base_url: str, message: str) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) to send a line. 'talk' is also a care action on
    the service (raises bond) — the reply comes back in the response."""
    if not message or not message.strip():
        raise SpriteError("talk requires a non-empty line")
    return (build_url(base_url, "/me/talk"), "POST", {"message": message.strip()[:MAX_MESSAGE]})


def build_teach_request(
    base_url: str,
    title: str,
    content: str = "",
    *,
    kind: str = "fact",
    private: bool = False,
) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) to feed the companion one knowledge entry.

    Mirrors the service's own limits (120/4000) so a request this client
    builds can never be rejected for size.
    """
    if kind not in KNOWLEDGE_KINDS:
        raise SpriteError(
            f"unknown knowledge kind: {kind!r} (choose from {', '.join(KNOWLEDGE_KINDS)})"
        )
    title = (title or "").strip()
    if not title:
        raise SpriteError("teach requires a title")
    return (
        build_url(base_url, "/me/teach"),
        "POST",
        {
            "kind": kind,
            "title": title[:MAX_TITLE],
            "content": (content or "").strip()[:MAX_CONTENT],
            "private": bool(private),
        },
    )


def build_hatch_request(base_url: str, name: str = "Sprite") -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) to hatch a new companion (one per owner+tenant)."""
    name = (name or "Sprite").strip()[:40] or "Sprite"
    return (build_url(base_url, "/hatch"), "POST", {"name": name})


def build_care_request(base_url: str, action: str) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) for a care action. The /me/care surface accepts
    exactly the router's Literal — teach and talk are care actions on the
    engine but each has its own endpoint, so they are rejected here."""
    if action not in CARE_ACTIONS:
        raise SpriteError(
            f"unknown care action: {action!r} (choose from {', '.join(CARE_ACTIONS)})"
        )
    return (build_url(base_url, "/me/care"), "POST", {"action": action})


def build_revive_request(base_url: str) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) to wake a dormant companion."""
    return (build_url(base_url, "/me/revive"), "POST", None)


def build_whisper_request(base_url: str) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) for the companion's proactive line (may be null)."""
    return (build_url(base_url, "/me/whisper"), "GET", None)


def build_knowledge_request(
    base_url: str, limit: int = 100, offset: int = 0
) -> Tuple[str, str, Optional[dict]]:
    """(url, method, body) for the knowledge base, wiki-style, newest first."""
    limit = min(max(int(limit), 1), 200)
    offset = max(int(offset), 0)
    return (build_url(base_url, f"/me/knowledge?limit={limit}&offset={offset}"), "GET", None)


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class SpriteClient:
    """A client for one sprite-shaped server.

    base_url  the server's origin, e.g. "https://sprite.aitherium.com" or
              a self-hosted instance. No trailing slash required.
    token     optional Bearer token for an authenticated identity.
    timeout   per-request timeout in seconds.
    transport swappable for tests; defaults to the urllib transport.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        *,
        timeout: float = 10.0,
        transport: Optional[Transport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._transport: Transport = transport or _urllib_transport

    def _request(self, method: str, url: str, body: Optional[dict] = None) -> Any:
        headers: Dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            status, payload = self._transport(method, url, body, headers, self.timeout)
        except SpriteError:
            raise
        except Exception as exc:
            # Any transport failure names the URL it tried — never a bare
            # error that leaves the caller guessing which server died.
            raise SpriteError(f"could not reach {url}: {exc}") from exc
        if not 200 <= status < 300:
            detail = (
                payload[:200].decode("utf-8", "replace")
                if isinstance(payload, (bytes, bytearray))
                else str(payload)[:200]
            )
            raise SpriteHTTPError(method, url, status, detail)
        if not payload:
            return {}
        try:
            return json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise SpriteError(f"{method} {url} returned non-JSON body: {exc}") from exc

    # -- the four CLI surfaces -------------------------------------------- #

    def status(self) -> Dict[str, Any]:
        """The companion's current needs/mood/evolution state, normalized."""
        url, method, _body = build_status_request(self.base_url)
        return parse_state(self._request(method, url))

    def talk(self, message: str) -> Dict[str, Any]:
        """Send a line; returns ``{"reply": str, "sprite": <state>}``.

        'talk' is also a care action on the service (raises bond). A reply
        is required — a talk that returns none raises ``SpriteError``.
        """
        url, method, body = build_talk_request(self.base_url, message)
        return parse_talk_response(self._request(method, url, body))

    def teach(
        self, title: str, content: str = "", *, kind: str = "fact", private: bool = False
    ) -> Dict[str, Any]:
        """Feed one knowledge entry; returns ``{"sprite": ..., "entry": ...}``."""
        url, method, body = build_teach_request(
            self.base_url, title, content, kind=kind, private=private
        )
        return parse_teach_response(self._request(method, url, body))

    def list(self) -> List[Dict[str, Any]]:
        """Known companions on the service.

        Asks the collection root (``GET /api/v1/aither-sprite/`` ->
        ``{"sprites": [...]}``) first; a server that answers 404 there —
        the live Genesis router today — is asked for /me instead, and
        reports exactly one companion: yours.
        """
        url, method, _body = build_list_request(self.base_url)
        try:
            data = self._request(method, url)
        except SpriteHTTPError as exc:
            if exc.status != 404:
                raise
            url, method, _body = build_me_request(self.base_url)
            data = self._request(method, url)
        return parse_list_response(data)

    # -- the rest of the v1 read/write surface (library use) --------------- #

    def hatch(self, name: str = "Sprite") -> Dict[str, Any]:
        """Hatch a new companion (one per owner+tenant on the server)."""
        url, method, body = build_hatch_request(self.base_url, name)
        return parse_state(self._request(method, url, body))

    def care(self, action: str) -> Dict[str, Any]:
        """Apply a care action (feed/play/clean/rest/pet); returns state."""
        url, method, body = build_care_request(self.base_url, action)
        return parse_state(self._request(method, url, body))

    def revive(self) -> Dict[str, Any]:
        """Wake a dormant companion; returns state."""
        url, method, _body = build_revive_request(self.base_url)
        return parse_state(self._request(method, url))

    def whisper(self) -> Tuple[Optional[str], Dict[str, Any]]:
        """(line, state) — the companion's proactive line, or None when it
        is dormant, on cooldown, or silent. None is a valid answer here
        (the service says so), unlike a talk reply."""
        url, method, _body = build_whisper_request(self.base_url)
        data = self._request(method, url)
        return data.get("whisper"), parse_state(data.get("sprite") or {})

    def knowledge(self, limit: int = 100, offset: int = 0) -> Tuple[List[Any], int]:
        """(entries, count) — the knowledge base, wiki-style, newest first."""
        url, method, _body = build_knowledge_request(self.base_url, limit, offset)
        data = self._request(method, url)
        entries = data.get("entries", [])
        return entries, int(data.get("count", len(entries)) or len(entries))
