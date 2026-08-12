# What's still hardcoded in the collision viewer

Collision geometry is decoded **100% from game data** — the nta collision
resource → `scripts/trb/nta2json.py` → per-level viewer JSONs. The level-1
JSON is verified byte-exact against the s02 RAM dump (pool + idx
`MATCH: True`); the other levels pass structural sanity (indices in range,
plausible bounds, layer-count consistency).

## Coverage: 9 / 15 levels have a collision resource in their AssetsAuto.nta

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

**No collision resource** (ntas are entity-assets-only / no geometry files;
likely unfinished or collision built at runtime from the entities):
dannyphantomlevel2/4, JimmyNeutronLevel4, SpongeBobLevel4, TimmyTurnerLevel4,
TestWorld.

## Hardcoded constants (no geometry)

| Item | Value | Why |
|---|---|---|
| Layer flags | 0x27 / 0x26 / 0x7 | Read live from the level-1 runtime layers; the nta layer records' flag field is unmapped. For 1–2-layer levels the first N are used (order: default, nopathfind, noocclude) |
| Layer names | "default" / "collision_nopathfind" / "collision_noocclude" | The runtime string table; same caveat as flags |
| div / yDown | 64 / true | The nta pool is ×64-scaled; the viewer flips Y |
| Level display names | web/levels.js | UI labels only |

## Known unknowns / next steps
- The nta section table + the layer records' +0/+4/+8/+0xc fields (the
  decoder reads the two concatenated streams directly; the record layout
  beyond count@+0x10 is partially mapped).
- Whether the 6 missing levels have collision anywhere (entity sections?
  a different file? none at all?).
- `data_len` in the header (140136 for DP1): pool+idx region is 172586 bytes;
  relation not yet understood.
