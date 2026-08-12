# DOL analysis

Tooling for `nicku-ntsc/P-GNOE/sys/main.dol` — the GameCube PowerPC
executable. The goal of this investigation was the GX vertex-format setup
(which array formats the engine feeds `GXSetArray`/`GXSetVtxAttrFmt`) and the
Toshi engine's mesh strip walking, to explain the mesh pools found by
[`trb/`](../trb/).

## Where's the ISO / what binary do I decompile?

- **ISO**: `nicktoonsunite.iso` (P-GNOE, GCN) lives at
  `games/console (other)/gcn+wii/` on the removable drive — currently mounted
  at
  `/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/`
  (the mount point contains the *mounting user's* name, so it can change;
  `NICK_EXTRACT` overrides everything).
- **The binary to decompile is the COMBINED ELF**: `vmtext_combined.elf` — the
  DOL text sections + the engine image `vmtext.bin` (loaded at 0x7f004000)
  merged into one ELF so Ghidra resolves cross-references both ways. Build it
  with:

      python3 build_combined_elf.py -o vmtext_combined.elf

  (inputs resolve from `NICK_EXTRACT`; the output is byte-identical to the
  previously-analyzed ELF, sha256 `ca1d134e...`, so the cached Ghidra project
  stays valid.)
- **Ghidra**: import the ELF with PowerPC:BE:32 (Ghidra picks `e500`; fine
  for Gekko code). The project is cached by sha in the pi-ghidra cache dir
  (`~/.pi/agent` + `/home/cyan/pi-ghidra-cache/artifacts/<sha>/project/`).
  Known analysis gap: DOL segment 2 (0x80042480-0x800b6f3f, the game code +
  dead OpCODE rodata) has NO functions created by auto-analysis; the vmtext
  segment (0x7f004000+, where the TTRB loader and the collision system live)
  and DOL segments 0-1 are fully analyzed.
- **Key anchors** (see `../../asset-extract/docs/collision-runtime.md`):
  TTRB container loader `FUN_7f297178` / `FUN_7f296f74` (vmtext); collision
  ray queries `FUN_7f0686d8 → FUN_7f067e60 → FUN_7f0650d0/414` →
  `FUN_7f2546e8` → `FUN_7f259760`; triangle→mesh map `FUN_7f2a4ee0`. OpCODE
  in the DOL is dead code (strings only, zero references).

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

## Remote debugging (live Dolphin)

`gdbstub/` — raw-protocol client + dispatcher scanner for the Dolphin GDB
stub, plus `gdbstub/README.md` with all the hard-won knowledge (the
`DebugModeEnabled` requirement, the one-connection lifecycle, the
savestate-kills-timing-event bug). Read it before using.
