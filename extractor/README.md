# nicku-extract

Turns a copy of `nicktoonsunite.iso` (P-GNOE) into the static JSON the web
viewer renders. The ISO is the only input.

## Usage

```sh
# from the ISO (needs WIT / wiimms-iso-tools on PATH)
nicku-extract --iso /path/nicktoonsunite.iso --out ./site

# from an already-extracted tree (skips WIT)
nicku-extract --data /path/P-GNOE/files/Data --out ./site

# via env vars
NICK_ISO=/path/nicktoonsunite.iso NICK_OUT=./site nicku-extract
```

Output:

```
site/
├── collision/<Level>.json          display meshes (mesh-v2)
├── collision/<Level>-coll.json     collision worlds (mesh-v2)
├── collision/manifest.json         levels with mesh data
├── entities/<Level>.ini            entity placements
└── build-info.json                 source hash + coverage report
```

## Decoders

| Module | What it decodes | Source |
|--------|-----------------|--------|
| `nicku.trb` | display meshes (TSFB/W0C0M records, 0x98 index strips) | re/tools/trb_mesh.py |
| `nicku.collision` | collision worlds — Format A (nta pool/idx resource) and Format B (nta main-resource nested TSFB) | scripts/trb/nta2json.py + ntaworld2json.py |
| `nicku.ttrb` | TSFB container walker | re/tools/trb_container.py |
| `nicku.dol` | main.dol section loader | re/tools/dol.py |

Format A is tried before Format B; the two are structurally distinct and
this reproduces the verified 9/6 level split (see docs/collision-status.md).
