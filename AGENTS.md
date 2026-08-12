# Project conventions

## Sources of truth (in priority order)
1. **Decomp** — the binary is the only true source of truth.
2. **Game data** — extracted files are the second source.
3. Toshi decoding / prior notes are just hints; verify against 1 and 2.

No heuristics unless nothing else works, and then only as a fallback.

## Getting started (drive + binary)
- ISO: `nicktoonsunite.iso` (P-GNOE) at `games/console (other)/gcn+wii/` on the
  removable drive. Find the mount with `findmnt` — the mount point embeds the
  mounting user's name, so never hardcode it. Prefer `NICK_ISO=/path/….iso`.
- The extractor turns the ISO into game data + viewer JSON in one shot:
  `nix run .#extract -- --iso "$NICK_ISO" --out ./site` (or `--data` for a
  pre-extracted `files/Data` tree). This is the only supported path from ISO
  to JSON — no more drive-symlink or hardcoded `/run/media/…` paths.
- Decompile `vmtext_combined.elf` (DOL + `vmtext.bin` engine image at
  0x7f004000): `python3 re/dol/build_combined_elf.py -o vmtext_combined.elf`,
  then import in Ghidra (PowerPC:BE:32). The collision system + TTRB loader
  live in vmtext; see re/dol/README.md and docs/collision-runtime.md.

## Layout
- `extractor/` — the product: ISO → JSON (do not put drive paths here).
- `viewer/` — the static web viewer. Generated data (`collision/`,
  `entities/`, `build-info.json`) is gitignored; fill it with the extractor.
- `docs/` — RE notes, centralized and current.
- `re/` — scratch RE tooling + investigation logs (not product code).
- `scripts/` — deploy/dev helpers.

## Verification
- After changing a decoder, re-run the extractor and diff against the last
  good output (or re-derive from the ISO — it is fully reproducible).
- Use vision to verify viewer edits (`web/test-headless.sh` + screenshots).
