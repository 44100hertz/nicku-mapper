# Scripts

Reverse-engineering / tooling scripts for the Nicktoons: Unite! level format.
These were previously scattered in `/tmp`; they're consolidated here so the
investigation work survives (the mounted disc-extract tree and `/tmp` are both
ephemeral). The maintained *product* code lives in `web/` (viewer + tests) and
`parser.lua`/`printer.lua`; this directory holds the scratch tooling that
cracked the TRB/DOL formats and the one-off image helpers.

## Layout

| Path                | Purpose                                                        |
|---------------------|----------------------------------------------------------------|
| `trb/`              | Scan GameCube TRB container files (mesh pools, strip indices). |
| `dol/`              | Disassemble / probe `main.dol` (PowerPC, GX vertex formats).   |
| `dol/probes/`       | One-shot w4a→w4v DOL probes (investigation log).               |
| `util/`             | Misc helpers (image diffing, etc.).                            |

## Common environment

Scripts that read game data default to the mounted disc-extract root:

    /run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract

Override it with `NICK_EXTRACT=/path/to/extract` when the drive is mounted
elsewhere. The repo's `asset-extract` symlink points at the same tree
(`asset-extract/tools/trb_mesh.py` is the canonical mesh exporter; these
scripts were the analysis that informed it).

DOL probes also need `capstone` (pip) and the `dol` module that lives in
`<extract>/tools/dol.py` (added to `sys.path` automatically).

## Per-directory details

- [`trb/`](trb/README.md) — TRB chunk/pool scanners.
- [`dol/`](dol/README.md) — DOL converters, disassemblers, GX analysis.
- [`dol/probes/`](dol/probes/README.md) — probe-by-probe map.
- `util/diffcmp.sh` — ImageMagick helper that crops two halves out of a
  side-by-side comparison PNG, computes a fuzz-diff (changed-pixel count +
  mean difference) and writes a `diffmap.png`. Used to eyeball before/after
  viewer screenshots.
