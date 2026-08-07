# DOL analysis

Tooling for `nicku-ntsc/P-GNOE/sys/main.dol` — the GameCube PowerPC
executable. The goal of this investigation was the GX vertex-format setup
(which array formats the engine feeds `GXSetArray`/`GXSetVtxAttrFmt`) and the
Toshi engine's mesh strip walking, to explain the mesh pools found by
[`trb/`](../trb/).

| Script         | Purpose                                                                    |
|----------------|----------------------------------------------------------------------------|
| `dol2elf.py`   | Generic DOL → ELF32 big-endian PowerPC converter (sections embedded, BSS included) for loading into Ghidra. `python3 dol2elf.py main.dol out.elf`. |
| `doldis.py`    | Tiny standalone capstone disassembler for the DOL text sections. `python3 doldis.py <ram_addr> <count>`. Section map hardcoded per this game. |
| `ghidra_dol.py`| Ghidra headless script: finds xrefs to level-loader format strings (`"W%dC%dM%d"`, `"LOD%d_Mesh_%d"`, `"Collision"`, ...) and decompiles the referencing functions. |
| `w4_scan.py`   | Main GX vertex-format analysis: disassembles the whole DOL, locates `GXSetVtxAttrFmt`/`GXSetVtxDesc`/`GXSetArray` and walks their callers' argument setup. |
| `probes/`      | 21 one-shot probes (w4b→w4v) — each answered one question during the RE session. See [`probes/README.md`](probes/README.md). |

All scripts read the DOL under `NICK_EXTRACT` (default: mounted disc-extract
root) and need `capstone`; the probes also import the `dol` loader module
from `<extract>/tools/dol.py`. See the top-level
[`scripts/README.md`](../README.md).

Note: `tools/dol.py` on the extract tree notes that the DOL header's data
section fields are garbage; the real text sections are 0, 1, 7, 8, 9, 10
with a fixed file→RAM mapping (embedded in `dol.py` and `doldis.py`).
