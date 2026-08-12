# What's still hardcoded in the collision viewer

Collision geometry is decoded **100% from game data** — the nta collision
resource → `extractor/nicku/collision.py` → per-level viewer JSONs. The level-1
JSON is verified byte-exact against the s02 RAM dump (pool + idx
`MATCH: True`); the other levels pass structural sanity (indices in range,
plausible bounds, layer-count consistency).

## Coverage: 15 / 15 levels — the two collision formats

**Format A — nta pool/idx resource** (`extractor/nicku/collision.py`, the
`{poolcnt, data_len, idxcnt, layercnt}` resource):

| Level | pool verts | layers (tris) |
|---|---|---|
| dannyphantomlevel1 | 11379 | 5735 / 74 / 182 |
| dannyphantomlevel3 | 15910 | 8293 / 49 / 350 |
| JimmyNeutronLab | 6729 | 4320 / 48 |
| JimmyNeutronLevel1_01 | 18240 | 3398 / 1999+140+10 / 2728+60 / 152 |
| SpongeBobLevel1 | 38828 | 6797+14176 / 48+132 |
| SpongeBobLevel2 | 27492 | 14421 |
| SpongeBobLevel3 | 24422 | 2649+3554+2638+1308 / 509+100+443 |
| TimmyTurnerLevel1 | 24385 | 10243 / 36 / 464 |
| TimmyTurnerLevel2 | 25708 | 11732 |

**Format B — nta main-resource world** (`extractor/nicku/collision.py`;
the nta's MAIN resource holds a nested TSFB + the world object table
`{1, p0, p1, -1, pool_off, nverts, idx_off, nidx, layercnt, layrecs}`,
pool = f32 @ SECT+pool_off, idx = u16 @ SECT+idx_off, layer names read
from the file):

| Level | pool verts | layers (tris) | names |
|---|---|---|---|
| dannyphantomlevel2 | 13082 | 6929 / 36 / 291 | default / collision_nopathfind / collision_noocclude |
| dannyphantomlevel4 | 7127 | 3224 | default |
| JimmyNeutronLevel4 | 2762 | 1276 | default |
| SpongeBobLevel4 | 2093 | 974 | default |
| TimmyTurnerLevel4 | 5119 | 2392 | default |
| TestWorld | 15880 | 6880 / 48 | default / collision_char |

All 15 levels' viewer JSONs regenerated (LOAD_VERSION 22). DP2/4 + the
boss levels were verified in the viewer (cyan overlay aligns with the
level mesh).

## Hardcoded constants (no geometry)

| Item | Value | Why |
|---|---|---|
| Layer flags | 0x27 / 0x26 / 0x7 | Read live from the level-1 runtime layers; the nta layer records' flag field is unmapped. For 1–2-layer levels the first N are used (order: default, nopathfind, noocclude) |
| Layer names | "default" / "collision_nopathfind" / "collision_noocclude" | Read from the file for the ntaworld2json levels (DP2 confirmed; TestWorld shows a unique "collision_char" layer); the nta2json levels use the DP1 runtime string table |
| div / yDown | 64 / true | The pool is ×64-scaled; the viewer flips Y |
| Level display names | web/levels.js | UI labels only |

## Known unknowns / next steps
- The nta section table + the layer records' +0/+4/+8 fields (count@+0xc
  and name@+0 are mapped; +8 = cumulative tri offset, +0x14 = next name).
- The world object table's p0/p1 (+4/+8) fields; the layer0 mesh record
  (the "default" layer's AABB/strip pointer @ the name offset) — display
  only, not needed for the viewer JSON.
- `data_len` in the Format-A header (140136 for DP1): pool+idx region is
  172586 bytes; relation not yet understood.
