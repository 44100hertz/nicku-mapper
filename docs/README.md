# Reverse-engineering notes

Centralized, current notes for the Nicktoons: Unite! (GCN, P-GNOE) level
format. The binary is the source of truth; these notes are the map.

## The two decoders (product code)

| Decoder | Module | Notes |
|---|---|---|
| Display meshes (TSFB/W0C0M + 0x98 index strips) | `extractor/nicku/trb.py` | `trb-format-notes.md` |
| Collision worlds — Format A (nta pool/idx) + Format B (nested TSFB) | `extractor/nicku/collision.py` | `collision-status.md`, `still-hardcoded.md` |
| main.dol sections / engine layout | `extractor/nicku/dol.py` | `collision-runtime.md` |

## Files

- **`trb-format-notes.md`** — the TRB/TTL container format write-up (HDRX/SECC/RELC/SYMB, W0C0M mesh records, 0x98 index blocks).
- **`collision-status.md`** — end-to-end collision-system status (RESOLVED): the runtime model, the two on-disc formats, and the decode verdicts.
- **`collision-runtime.md`** — live-RE session results: the runtime collision build, and why the old `extract_collision.py` reading was retracted.
- **`trb-collision-test.md`** — "is it the same as Barnyard?" hypothesis test (TTRB/TTMDBase cross-check).
- **`still-hardcoded.md`** — what is *not* derived from game data (layer flags/names, div/yDown), with the per-level coverage table.
- **`spec.org`** — the original project spec (historical).

Scratch tooling notes live with the code they document:
`re/README.md`, `re/dol/README.md`, `re/dol/gdbstub/README.md` (live-debug
doctrine), `re/dol/probes/README.md`, `re/trb/README.md`.

## Path migration (post-monorepo)

Older notes reference the pre-pivot layout. The mapping:

| Old path | New path |
|---|---|
| `scripts/trb/nta2json.py` | `extractor/nicku/collision.py` (Format A) |
| `scripts/trb/ntaworld2json.py` | `extractor/nicku/collision.py` (Format B) |
| `asset-extract/tools/trb_mesh.py` | `extractor/nicku/trb.py` |
| `asset-extract/tools/dol.py` | `extractor/nicku/dol.py` |
| `scripts/dol/*` | `re/dol/*` |
| `nicku-ntsc/P-GNOE/files/Data/…` | `files/Data/…` (the ISO-extracted tree) |
| `NICK_EXTRACT` (drive mount) | `NICK_ISO` / `NICK_DATA` (the ISO / tree) |

## Reproducibility

`nicku-extract` output is deterministic: re-extracting the same ISO with the
same WIT version reproduces every JSON byte-for-byte (verified this session).
