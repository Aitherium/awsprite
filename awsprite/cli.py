"""awsprite CLI — status/talk/teach/list against an AitherSprite-shaped server.

    awsprite status
    awsprite talk "good morning!"
    awsprite teach notes.md
    awsprite list --url https://sprite.example

Connection comes from flags or env vars (AWSPRITE_URL, AWSPRITE_TOKEN) —
flags win. No config file: a companion CLI that silently reads a stale
saved endpoint is worse than one that asks every time.

Exit codes: 0 success, 1 the service refused or was unreachable
(SpriteError), 2 the command could not run at all (bad args, missing env,
unreadable file). A failed call ALWAYS names the URL it tried — never a
silent empty reply.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from awsprite.client import SpriteClient, SpriteError
from awsprite.model import KNOWLEDGE_KINDS
from awsprite.teach import parse_teach_entries


def _bar(value: float) -> str:
    """10-cell bar for a need in [0, 1].

    ASCII-only on purpose: the block glyphs are not encodable in cp1252,
    the Windows console default — a status command that crashes on the
    encoding of its own output is not a status command.
    """
    v = min(max(float(value), 0.0), 1.0)
    filled = int(round(v * 10))
    return "#" * filled + "-" * (10 - filled)


def _client_from_args(args: argparse.Namespace) -> SpriteClient:
    url = args.url or os.environ.get("AWSPRITE_URL")
    if not url:
        print("awsprite: no sprite URL — pass --url or set AWSPRITE_URL", file=sys.stderr)
        raise SystemExit(2)
    token = args.token or os.environ.get("AWSPRITE_TOKEN")
    return SpriteClient(url, token=token)


def _cmd_status(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    try:
        s = client.status()
    except SpriteError as exc:
        print(f"awsprite: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(s, indent=2))
        return 0
    if s["dormant"]:
        print(f"{s['name']} ({s['stage']}, {s['form']}) — DORMANT — revive it first")
    else:
        print(f"{s['name']} ({s['stage']}, {s['form']}) — {s['mood_label']}")
    for need in ("hunger", "energy", "hygiene", "bond"):
        value = s["needs"][need]
        print(f"  {need:<8} {_bar(value)} {value:.2f}")
    print(
        f"  age {s['age_days']:.1f} days · knows {s['knowledge_count']} things"
        f" · intellect: {s['intellect_label']}"
    )
    return 0


def _cmd_talk(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    try:
        result = client.talk(args.line)
    except SpriteError as exc:
        print(f"awsprite: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result))
    else:
        print(result["reply"])
    return 0


def _cmd_teach(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    try:
        with open(args.file, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"awsprite: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    try:
        entries = parse_teach_entries(text, default_kind=args.kind)
    except SpriteError as exc:
        print(f"awsprite: {exc}", file=sys.stderr)
        return 2
    if not entries:
        print(
            f"awsprite: no teachable entries found in {args.file} "
            "(a '# heading' per section, or blank-line-separated notes)",
            file=sys.stderr,
        )
        return 1
    taught = 0
    for entry in entries:
        try:
            client.teach(entry["title"], entry["content"], kind=entry["kind"], private=args.private)
        except SpriteError as exc:
            print(f"awsprite: teach {entry['title']!r} failed: {exc}", file=sys.stderr)
            return 1
        taught += 1
    if args.json:
        print(json.dumps({"taught": taught, "file": args.file, "entries": entries}))
    else:
        word = "entry" if taught == 1 else "entries"
        print(f"taught {taught} {word} from {args.file}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    try:
        companions = client.list()
    except SpriteError as exc:
        print(f"awsprite: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(companions))
        return 0
    if not companions:
        print("(no companions)")
        return 0
    for c in companions:
        dormant = " (dormant)" if c["dormant"] else ""
        print(f"{c['name']} — {c['stage']}, {c['form']} — {c['mood_label']}{dormant}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone
    from pathlib import Path

    from awsprite.export import build_pack, fetch_all_knowledge, write_pack

    client = _client_from_args(args)
    try:
        state = client._request("GET", client.base_url + "/api/v1/aither-sprite/me")
        entries = fetch_all_knowledge(client.knowledge)
        files = build_pack(
            state, entries, name=args.name,
            exported_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        written = write_pack(files, Path(args.out_dir), overwrite=args.overwrite)
    except SpriteError as exc:
        print(f"awsprite: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"out_dir": str(args.out_dir), "files": [str(p) for p in written],
                          "entries": len(entries)}, indent=2))
    else:
        print(f"exported {len(entries)} entries -> {args.out_dir} ({len(written)} files)")
        print(f"next: cd {args.out_dir} && pip install awdk && adk up")
    return 0


def _print_guide(view: dict, note: str = "") -> None:
    if note:
        print(note)
    ladder = view.get("ladder") or {}
    stats = view.get("stats") or {}
    print(f"guide: {view.get('temperament')} · today: "
          f"{', '.join(view.get('available_acts') or []) or 'already acted'}")
    offer = view.get("offer")
    if offer:
        what = f"spar ({offer.get('stat')})" if offer.get("act") == "spar" else \
            f"venture ({offer.get('foe')})"
        print(f"  OFFER waiting: {what} -- answer with `awsprite answer yes|no`")
    print("  stats " + "  ".join(f"{k} {stats.get(k, 0)}/{view.get('stat_cap')}"
                                 for k in ("strength", "dexterity", "speed")))
    nxt = ladder.get("next_foe") or "cleared"
    print(f"  ladder rung {ladder.get('rung')}/{ladder.get('of')}: {nxt} · "
          f"{ladder.get('wins', 0)}W {ladder.get('losses', 0)}L")
    if view.get("charms"):
        worn = ", ".join(view.get("equipped") or []) or "-"
        print(f"  charms {', '.join(view['charms'])} (worn: {worn})")


def _guide_call(args: argparse.Namespace, fn) -> int:
    client = _client_from_args(args)
    try:
        out = fn(client)
    except SpriteError as exc:
        print(f"awsprite: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    result = out.get("result") or {}
    note = result.get("line") or ""
    outcome = result.get("outcome") or result
    if isinstance(outcome, dict) and outcome.get("foe"):
        note = (f"beat {outcome['foe']} in {outcome.get('rounds')} rounds" if outcome.get("won")
                else f"lost to {outcome['foe']}" + (f", found a {outcome['charm']} charm"
                                                    if outcome.get("charm") else ""))
    elif isinstance(outcome, dict) and outcome.get("stat") and "gain" in outcome:
        note = f"{outcome['stat']} +{outcome['gain']} -> {outcome['value']}/{outcome['cap']}"
    _print_guide(out, note)
    return 0


def _cmd_guide(args: argparse.Namespace) -> int:
    return _guide_call(args, lambda c: c.guide())


def _cmd_beat(args: argparse.Namespace) -> int:
    return _guide_call(args, lambda c: c.guide_beat(args.act))


def _cmd_answer(args: argparse.Namespace) -> int:
    return _guide_call(args, lambda c: c.guide_answer(args.choice == "yes"))


def _cmd_train(args: argparse.Namespace) -> int:
    return _guide_call(args, lambda c: c.train(args.stat))


def _cmd_challenge(args: argparse.Namespace) -> int:
    return _guide_call(args, lambda c: c.challenge())


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="awsprite", description=__doc__)
    ap.add_argument("--url", help="sprite-shaped service origin (or AWSPRITE_URL)")
    ap.add_argument("--token", help="bearer token (or AWSPRITE_TOKEN)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")

    sub = ap.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="the companion's needs/mood/evolution state")
    p_status.set_defaults(func=_cmd_status)

    p_talk = sub.add_parser("talk", help="send a line and print the reply")
    p_talk.add_argument("line")
    p_talk.set_defaults(func=_cmd_talk)

    p_teach = sub.add_parser("teach", help="teach from a markdown/notes file")
    p_teach.add_argument("file")
    p_teach.add_argument(
        "--kind", default="fact", choices=KNOWLEDGE_KINDS,
        help="knowledge kind applied to every entry (default: fact)",
    )
    p_teach.add_argument(
        "--private", action="store_true",
        help="request private visibility (requires an entitlement on the server)",
    )
    p_teach.set_defaults(func=_cmd_teach)

    p_list = sub.add_parser("list", help="list known companions on the service")
    p_list.set_defaults(func=_cmd_list)

    p_export = sub.add_parser(
        "export", help="graduate the companion into an adk agent pack (state + knowledge)"
    )
    p_export.add_argument("out_dir", help="directory to write the pack scaffold into")
    p_export.add_argument("--name", help="agent name (default: the sprite's name)")
    p_export.add_argument(
        "--overwrite", action="store_true", help="write into a non-empty directory"
    )
    p_export.set_defaults(func=_cmd_export)

    p_guide = sub.add_parser("guide", help="the spirit guide: temperament, offer, stats, ladder")
    p_guide.set_defaults(func=_cmd_guide)
    p_beat = sub.add_parser("beat", help="let the guide take its one act for today")
    p_beat.add_argument("act", nargs="?", help="an act id `guide` lists (default: its choice)")
    p_beat.set_defaults(func=_cmd_beat)
    p_answer = sub.add_parser("answer", help="accept or decline the guide's pending offer")
    p_answer.add_argument("choice", choices=("yes", "no"))
    p_answer.set_defaults(func=_cmd_answer)
    p_train = sub.add_parser("train", help="train one stat")
    p_train.add_argument("stat", choices=("strength", "dexterity", "speed"))
    p_train.set_defaults(func=_cmd_train)
    p_fight = sub.add_parser("challenge", help="fight the next foe on the ladder")
    p_fight.set_defaults(func=_cmd_challenge)

    return ap


def main(argv: Optional[List[str]] = None) -> int:
    # GENERATED doctor intercept (gen_aw_doctor.py) -- do not edit
    _dv = locals().get("argv")
    if (_dv if _dv is not None else __import__("sys").argv[1:])[:1] == ["doctor"]:
        from ._doctor import report
        return report()
    # GENERATED repo-state intercept (gen_aw_doctor.py) -- do not edit
    try:
        from awgit import state as _aw_state
    except Exception:
        _aw_state = None
    if _aw_state is not None:
        _sv = locals().get("argv")
        if _aw_state.cli_banner(_sv if _sv is not None else __import__("sys").argv[1:]):
            return 0
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
