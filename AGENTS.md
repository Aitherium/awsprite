# awsprite for agents

Read this if you are an agent (or a human) editing this package. Short on
purpose: the commands, the traps that cost a session, and where the rest lives.
Nothing here is read at runtime — it is for you.

## What this is

PyPI distribution **`awsprite`** (version in `pyproject.toml`), import package
`awsprite`, Python >= 3.10. Hatch a companion that grows only from what you
teach it, then take it home — a knowledge base you can list, edit, and watch
shape what it becomes.

This repository is a **synced mirror** of the AitherOS monorepo (lane
`.github/workflows/sync-awsprite.yml`). Hand edits made here are overwritten on
the next sync — change the source and let the lane publish.

## Build, test, verify

```bash
python -m pytest tests -q        # the suite: 84 tests, green at v0.2.0
pip install -e .                 # editable install for developing against it
```

The suite was run from a source checkout with no prior install. The publish
lane (`publish-brick.yml`) additionally builds the wheel, installs it and
imports it — a tree that tests green can still ship a broken wheel.

## Rules that keep this useful

- **The embed script is a byte-exact artifact.** `test_embed.py` asserts it is
  ASCII and LF, and raw-compares the package copy against the template copy —
  both files carry an explicit `text eol=lf` rule in the root `.gitattributes`
  precisely so a Windows checkout gets what CI gets (measured 2026-10-06: with
  no rule the copies were both CRLF on Windows, the byte-compare was secretly
  green, and the ASCII+LF assertion was red). Edit one copy; copy it over the
  other; the test is the enforcement.
- **What the companion becomes must stay checkable.** The knowledge base is
  listable and editable by design — a "growth" path that only the model can
  read is the black-box failure this brick exists to replace.
- **The registry drives the public surface.** This repo's README header and
  `aither-manifest.json` are generated from the ecosystem registry (one yaml
  in the AitherOS monorepo) and rewritten on every sync. Change the registry;
  do not hand-edit the generated blocks.

## Read next

- `README.md` — the human front door
- `awsprite/embed.py` + `awsprite/web/sprite-embed.js` — the shipped embed
