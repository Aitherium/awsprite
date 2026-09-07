# awsprite

A portable client for an **AitherSprite-shaped companion service** — status,
talk, teach, and list. Give a companion a face and a mind, then let several
of them talk.

> Hatch a companion, teach it something, and watch what it becomes.

`awsprite` is a **client, not the engine** — the aw-family rule. `awrelay`
did not lift `AitherRelay.py`; it shipped a small standalone client that
speaks to any relay-shaped server. Same move here: the companion's state —
needs that decay over real wall-clock time, a mood derived from those needs,
deterministic evolution through egg → baby → child → teen → adult → elder —
is **server-authoritative**. This package reads that state, talks to the
companion, and feeds it knowledge. It never re-implements the game, and it
imports nothing from the monorepo: stdlib only, publishable standalone.

## Adopt

```bash
pip install awsprite

awsprite --url https://sprite.example status
awsprite --url https://sprite.example talk "good morning!"
awsprite --url https://sprite.example teach notes.md
awsprite --url https://sprite.example list
```

Point `--url` at any sprite-shaped server, or set `AWSPRITE_URL` (and
`AWSPRITE_TOKEN` for a hosted companion that needs a bearer token). Flags
win over env; there is no config file — a companion CLI that silently reads
a stale saved endpoint is worse than one that asks every time.

## What it speaks

The sprite-shaped REST surface (Genesis's router is the reference; prefix
`/api/v1/aither-sprite`):

| method | path | what it does |
|---|---|---|
| GET | `/me/status` | needs/mood/evolution state (lighter subset) |
| GET | `/me` | full state (public dict) |
| POST | `/me/talk` | send a line, get the reply (`{"reply", "sprite"}`) |
| POST | `/me/teach` | feed one knowledge entry (`{"sprite", "entry"}`) |
| GET | `/` | collection root — every known companion (`{"sprites": [...]}`) |
| POST | `/hatch` | hatch a companion (one per owner+tenant) |
| POST | `/me/care` | feed / play / clean / rest / pet |
| POST | `/me/revive` | wake a dormant companion |
| GET | `/me/whisper` | the companion's proactive line (may be null) |
| GET | `/me/knowledge` | the knowledge base, wiki-style, newest first |

`teach` and `talk` are care actions on the engine too — teaching sates
hunger and raises bond; talking raises bond. The client never needs to know:
each has its own endpoint, and the response always carries the fresh state.

A server that answers 404 on the collection root (the live router today)
reports exactly one companion for `list`: yours, via `/me`.

## Teach-file format

`awsprite teach <file>` understands two deterministic layouts:

- **Markdown sections** — any `#` heading opens a section; the heading text
  is the entry title, the lines until the next heading are the content.
- **Plain notes** — no headings; the file is split on blank lines, the first
  non-blank line of each chunk is the title, the rest is the content.

Titles and content are truncated to the service's own limits (120 / 4000
characters), never sent whole. `--kind fact|skill|link|lore` applies to
every entry (default `fact`); `--private` requests private visibility
(requires an entitlement on the server).

## As a library

```python
from awsprite import SpriteClient

client = SpriteClient("https://sprite.example", token="...")
state = client.status()
print(state["mood_label"], state["needs"])
reply = client.talk("good morning!")["reply"]
client.teach("The ocean", "covers 70% of Earth", kind="fact")
```

Every method raises `SpriteError` when the server is unreachable or refuses,
and the error **names the URL it tried** — never a silent empty reply.

## Honest failure

There is no offline mode and no fallback. A companion client with nothing to
talk to is not a degraded companion client, it is not a companion client. A
talk that returns no reply is an error, not an empty line: the one thing
worse than a dead server is a server that looks fine and says nothing.

Exit codes: `0` success, `1` the service refused or was unreachable, `2` the
command could not run at all (bad args, missing `AWSPRITE_URL`, unreadable
file).

## Development

```bash
python -m pytest tests/ -q
```

Stdlib-only by design — no requests, no pydantic, no httpx. The one network
call is `urllib.request.urlopen`, swappable via `SpriteClient(transport=...)`
so the whole contract is unit-tested with no network and no mock HTTP stack.

## Licence

MIT © Aitherium.
