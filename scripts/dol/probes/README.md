# DOL probes (w4b → w4v)

One-shot investigation scripts from the GX vertex-format RE session. Each
disassembles `main.dol` (via capstone + the `dol` loader from
`<extract>/tools/`) and prints an answer to a single question. They're kept
as the investigation log; `w4_scan.py` is the consolidated main analysis.

| Probe | Question it answered                                                        |
|-------|----------------------------------------------------------------------------|
| w4b   | Deeper DOL probes — locating relevant code regions.                         |
| w4c   | Find the GX library + `GXSetArray`/`GXSetVtxAttrFmt` + their callers.       |
| w4d   | Identify `GXSetArray` + `GXSetVtxAttrFmt` + their callers.                  |
| w4e   | Callers of GX functions from game code + argument setup.                    |
| w4f   | Dump the vertex setup function + target GX functions.                       |
| w4g   | `GXSetArray` candidates + callers of `0x80041A44`.                          |
| w4h   | Find the symbol-name string block + xrefs (hi/hi+1) → TTRB loader code.     |
| w4i   | Find data pointers to symbol-name strings + dump referencing code.          |
| w4j   | Find TRB container tag constants → file parser/loader code.                 |
| w4k   | Search for TFourCC constants (both endiannesses).                           |
| w4l   | Find `GXSetArray` definition + all `GXSetVtxAttrFmt`/`GXSetArray` call sites.|
| w4m   | Find strip-walking code via `addi rX,rX,6` / `mulli rX,rX,6`.               |
| w4n   | Dump the function containing `0x8003f2c0`.                                  |
| w4o   | Find the Toshi NameHash function (`mulli` by 31 / `slwi 5 - sub`).          |
| w4p   | Full GX function roster.                                                    |
| w4q   | All callers of `GXSetVtxAttrFmt`(0x80039764)/`GXSetVtxDesc`(0x80038ea4)/getters 0x80038e94/0x80038e9c/0x80038954. |
| w4r   | Dump indexed-array + draw GX functions.                                     |
| w4s   | Dump GXInit tail + game GX-state functions.                                 |
| w4t   | Find the GXBegin-equivalent (fifo cmd 0x98/0x90/0x80) + draw callers.       |
| w4u   | Dump `0x8003abbc` (0x98 primitive cmd fn) + callers.                        |
| w4v   | Draw entry fns `0x8003aaec`/`0x8003e2d0` + their game callers.              |
