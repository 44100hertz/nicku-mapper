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

    <extract-root>

Override it with `NICK_EXTRACT=/path/to/extract` when the drive is mounted
elsewhere. The repo's `asset-extract` symlink points at the same tree
(`asset-extract/tools/trb_mesh.py` is the canonical mesh exporter; these
scripts were the analysis that informed it).

**The ISO** (`nicktoonsunite.iso`, P-GNOE) is a sibling of the extract dir
under `games/console (other)/gcn+wii/` — the drive must be mounted; the mount
point embeds the mounting user's name, so resolve it via `NICK_EXTRACT` or
`findmnt` rather than hardcoding. DOL probes also need `capstone` (pip) and
the `dol` module that lives in `<extract>/tools/dol.py` (added to `sys.path`
automatically).

**What to decompile**: `vmtext_combined.elf` (DOL + engine image) — build it
with `dol/build_combined_elf.py` (see `dol/README.md` for the Ghidra cache
and the known segment-2 analysis gap).

## Per-directory details

- [`trb/`](trb/README.md) — TRB chunk/pool scanners.
- [`dol/`](dol/README.md) — DOL converters, disassemblers, GX analysis.
- [`dol/probes/`](dol/probes/README.md) — probe-by-probe map.
- `util/diffcmp.sh` — ImageMagick helper that crops two halves out of a
  side-by-side comparison PNG, computes a fuzz-diff (changed-pixel count +
  mean difference) and writes a `diffmap.png`. Used to eyeball before/after
  viewer screenshots.
