# nicku-mapper

Reverse-engineering toolkit and 3D web viewer for **Nicktoons: Unite!** (GameCube, P-GNOE). Give it the ISO; it extracts the game data, decodes the level meshes and collision worlds, and renders them in the browser.

## Layout

```
extractor/   ISO -> JSON pipeline (Python package + `nicku-extract` CLI)
viewer/      static web viewer (three.js, no build step)
docs/        reverse-engineering notes (single source of truth)
re/          scratch RE tooling (DOL disasm, gdbstub, one-off hunts)
scripts/     deploy + dev helpers
```

- **`extractor/nicku/trb.py`** — display-mesh decoder (TSFB/W0C0M records, 0x98 index strips).
- **`extractor/nicku/collision.py`** — collision-world decoder, two formats (nta pool/idx resource + nta main-resource nested TSFB), detected structurally.
- **`extractor/nicku/dol.py`** — `main.dol` section loader (engine RE).
- Everything in `re/` is the investigation log that produced the above.

## Quick start

```sh
nix develop                 # dev shell (python + wit + node + ghidra)

# build the site from your ISO (the only input)
nix run .#extract -- --iso /path/nicktoonsunite.iso --out ./site

# or from an already-extracted tree
nix run .#extract -- --data /path/P-GNOE/files/Data --out ./site

# serve the viewer
python3 -m http.server 8080 -d site
```

`NICK_ISO` / `NICK_DATA` / `NICK_OUT` env vars work instead of flags. Everything is a pure `nix build`; the ISO is a runtime input only.

## Viewer

Serve the static site (`python3 -m http.server -d viewer`) after running the extractor into `viewer/`. Deep-link with a hash: `/#SpongeBobLevel2`.

Controls: left-drag to rotate, right-drag to pan, wheel to zoom, click an entity to inspect it, double-click to fly to it. The panel toggles points/links/paths/grid/mesh geometry/solid faces/back-face culling/additive blend, and filters entity types.

Coordinates: the game stores +y down and mirrors z, so the viewer renders `(x, -y, -z)`. Entity AABB boxes follow the engine convention — dimensions are half-extents, `Position.y` is the top of the volume.

## Deploying to GitHub Pages

The main branch carries no generated game data. The `gh-pages` branch holds the built site:

```sh
NICK_ISO=/path/nicktoonsunite.iso scripts/deploy-gh-pages.sh
```

## RE notes

See [`docs/`](docs/) — `trb-format-notes.md`, `collision-status.md`, `collision-runtime.md`, `still-hardcoded.md` and friends are the consolidated, up-to-date notes. The extractor's `build-info.json` output is the machine-readable coverage report.

## License

Tooling and notes: MIT. The game (and anything the extractor produces from it) is © THQ / Nickelodeon; supply your own ISO.
