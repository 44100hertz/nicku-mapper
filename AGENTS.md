 - Decomp is the only true source of truth
 - Game data is the second source of truth
 - Toshi decoding is just a hint/guide
 - We shouldn't need to use any heuristics
 - Use vision to verify your edits

Getting started (drive + binary):
 - ISO: nicktoonsunite.iso (P-GNOE) at "games/console (other)/gcn+wii/" on the
   removable drive; find the mount with `findmnt` or `NICK_EXTRACT` (the
   mount point embeds the mounting user's name, don't hardcode it).
 - Decompile vmtext_combined.elf (DOL + vmtext.bin engine image at 0x7f004000):
   `scripts/dol/build_combined_elf.py -o vmtext_combined.elf`, then import in
   Ghidra (PowerPC:BE:32). Collision system + TTRB loader live in vmtext;
   see scripts/dol/README.md + asset-extract/docs/collision-runtime.md.
