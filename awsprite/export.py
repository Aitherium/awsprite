"""Graduate a companion into an adk agent pack -- the sprite, taken home.

A sprite is server-authoritative: its needs, mood and stage live on the service.
What is YOURS is what you taught it. ``export`` pulls the companion's public
state and its whole knowledge base and writes an **adk agent-pack scaffold**::

    <out>/
      agent.yaml            adk pack manifest (name, slug, seed knowledge dir)
      identity.yaml         who the agent is, derived from the sprite's form/stage
      knowledge/INDEX.md    one line per taught entry, grouped by kind
      knowledge/<kind>/<slug>.md
                            one page per entry, front matter + the content verbatim
      sprite.json           the raw export (state + entries) for a round trip
      README.md             how to grow it from here with awdk

Pure functions build the file map; one thin writer puts it on disk. Nothing
here imports from the monorepo -- stdlib only, like the rest of the package.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from awsprite.model import KNOWLEDGE_KINDS, SpriteError, parse_state

PAGE = 200  # the server caps a knowledge page at 200


def slugify(text: str, fallback: str = "entry") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return (s[:60].rstrip("-")) or fallback


def _yaml_str(value: Any) -> str:
    """A double-quoted YAML scalar. The scaffold is hand-editable YAML, so every
    user-supplied string is quoted -- a sprite named `yes` or `1.0` must not
    become a boolean or a float."""
    return json.dumps(str(value), ensure_ascii=False)


def _front_matter(fields: Dict[str, Any]) -> str:
    lines = ["---"]
    for k, v in fields.items():
        lines.append(f"{k}: {_yaml_str(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def fetch_all_knowledge(
    knowledge: Callable[[int, int], Tuple[List[Any], int]], page: int = PAGE
) -> List[Dict[str, Any]]:
    """Walk ``client.knowledge(limit, offset)`` until the server runs dry.

    Stops on a short page OR when ``count`` entries have been seen, whichever
    comes first -- a server that reports a stale count cannot make this loop
    forever, and one that under-reports cannot make it drop pages."""
    out: List[Dict[str, Any]] = []
    offset = 0
    while True:
        entries, count = knowledge(page, offset)
        entries = [e for e in entries if isinstance(e, dict)]
        out.extend(entries)
        offset += len(entries)
        if len(entries) < page or (count and offset >= count) or not entries:
            break
    return out


def _entry_fields(e: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(e.get("kind") or "fact")
    if kind not in KNOWLEDGE_KINDS:
        kind = "fact"
    return {
        "id": str(e.get("id") or ""),
        "kind": kind,
        "title": str(e.get("title") or "").strip() or "untitled",
        "content": str(e.get("content") or ""),
        "taught_at": str(e.get("created_at") or e.get("taught_at") or ""),
    }


_FORM_STYLE = {
    "scholar": ("studious", "precise"),
    "balanced": ("curious", "friendly"),
}


def build_pack(
    state_raw: Any, entries_raw: Iterable[Any], *, name: Optional[str] = None,
    exported_at: str = "",
) -> Dict[str, str]:
    """(relative path -> file text) for the whole scaffold. Pure."""
    state = parse_state(state_raw)
    entries = [_entry_fields(e) for e in entries_raw if isinstance(e, dict)]
    agent_name = (name or state["name"] or "Sprite").strip() or "Sprite"
    slug = slugify(agent_name, "sprite")
    style, tone = _FORM_STYLE.get(state["form"], ("curious", "friendly"))
    stage, form = state["stage"], state["form"]
    n_entries = len(entries)
    blurb = (f"{agent_name} -- graduated from an AitherSprite companion ({stage}, {form}) "
             f"with {n_entries} taught entries")
    who = (f"A companion that grew from what its owner taught it: {n_entries} entries, "
           f"{stage} stage, {form} form.")

    files: Dict[str, str] = {}
    seen: Dict[str, int] = {}
    by_kind: Dict[str, List[Tuple[str, str]]] = {k: [] for k in KNOWLEDGE_KINDS}
    for e in entries:
        base = slugify(e["title"])
        n = seen.get(base, 0)
        seen[base] = n + 1
        page_slug = base if n == 0 else f"{base}-{n + 1}"
        rel = f"knowledge/{e['kind']}/{page_slug}.md"
        files[rel] = _front_matter(
            {"title": e["title"], "kind": e["kind"], "sprite_entry_id": e["id"],
             "taught_at": e["taught_at"]}
        ) + "\n" + e["content"].rstrip() + "\n"
        by_kind.setdefault(e["kind"], []).append((e["title"], rel))

    index = [f"# {agent_name} -- what it was taught", "",
             f"{len(entries)} entries, exported from an AitherSprite companion "
             f"({state['stage']}, {state['form']}).", ""]
    for kind in KNOWLEDGE_KINDS:
        rows = by_kind.get(kind) or []
        if not rows:
            continue
        index.append(f"## {kind} ({len(rows)})")
        index.append("")
        for title, rel in rows:
            index.append(f"- [{title}]({rel.split('/', 1)[1]})")
        index.append("")
    files["knowledge/INDEX.md"] = "\n".join(index).rstrip() + "\n"

    files["agent.yaml"] = "\n".join([
        f"name: {_yaml_str(agent_name)}",
        f"slug: {_yaml_str(slug)}",
        'version: "1.0.0"',
        f"description: {_yaml_str(blurb)}",
        "base_image: ghcr.io/aitherium/adk-cognitive:latest",
        f"identity: {_yaml_str(slug)}",
        "",
        "# What the sprite was taught, one markdown page per entry. adk seeds the",
        "# agent's knowledge base from this directory; keep teaching by adding pages.",
        "knowledge:",
        "  seed_dir: knowledge",
        "  index: knowledge/INDEX.md",
        "",
        "llm:",
        "  backend: ollama",
        "  model: llama3.2:3b",
        '  fallback_model: ""',
        "",
        "tools:",
        "  builtin: [file_read, web_search]",
        "  packs: []",
        "  custom: []",
        "",
        "deployment:",
        "  standalone: true",
        "  platform_connect: false",
        "",
        "sprite:",
        f"  id: {_yaml_str(state['id'])}",
        f"  stage: {_yaml_str(state['stage'])}",
        f"  form: {_yaml_str(state['form'])}",
        f"  knowledge_count: {int(state['knowledge_count'])}",
        f"  exported_at: {_yaml_str(exported_at)}",
        "",
    ])

    files["identity.yaml"] = "\n".join([
        f"name: {_yaml_str(slug)}",
        f"display_name: {_yaml_str(agent_name)}",
        f"description: {_yaml_str(who)}",
        "role: companion",
        "will: Answer from what I was taught, say when I was not taught it, and keep learning.",
        "personality:",
        f"  style: {_yaml_str(style)}",
        f"  tone: {_yaml_str(tone)}",
        "  verbosity: balanced",
        "capabilities:",
        "  - general_conversation",
        "  - recall_taught_knowledge",
        "",
    ])

    files["sprite.json"] = json.dumps(
        {"exported_at": exported_at, "state": state, "entries": entries},
        indent=2, ensure_ascii=False,
    ) + "\n"

    files["README.md"] = "\n".join([
        f"# {agent_name}",
        "",
        f"An adk agent pack graduated from an AitherSprite companion on {exported_at or 'export'}.",
        f"Stage `{state['stage']}`, form `{state['form']}`, {len(entries)} taught entries under",
        "`knowledge/` (one markdown page each; `knowledge/INDEX.md` lists them).",
        "",
        "## Grow it",
        "",
        "```bash",
        "pip install awdk",
        "adk up                 # runs the agent from agent.yaml, seeded from knowledge/",
        "```",
        "",
        "- Teach it more by adding pages under `knowledge/<kind>/` and re-running `adk up`.",
        "- Give it hands by listing tools under `tools:` in `agent.yaml`.",
        "- Change who it is in `identity.yaml`.",
        "- `sprite.json` is the raw export: keep it if you ever want to sync the",
        "  knowledge base back to the hosted companion.",
        "",
    ])
    return files


def write_pack(files: Dict[str, str], out_dir: Path, *, overwrite: bool = False) -> List[Path]:
    """Write the file map under ``out_dir``. Refuses to clobber an existing
    non-empty directory unless ``overwrite`` -- a graduation that silently
    overwrites the pack you were editing is a data loss, not a convenience."""
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise SpriteError(f"{out_dir} exists and is not empty (pass --overwrite)")
    written: List[Path] = []
    for rel, text in files.items():
        p = out_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        written.append(p)
    return written
