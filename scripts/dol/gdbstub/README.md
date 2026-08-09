# Dolphin GDB stub remote debugging — hard-won knowledge

Everything learned the painful way during the collision-format investigation.
Read this BEFORE touching the emulator again, or you will re-live the dance
(connect → connection dies → relaunch game → repeat).

## TL;DR checklist

1. Dolphin must run with **Cached Interpreter** (JIT breaks the stub: host
   addresses, flaky stops). The GDB stub was built for the interpreter.
2. `[Interface] DebugModeEnabled = True` must be in Dolphin.ini — **without
   it the interpreter NEVER checks breakpoints** (see §"The one setting").
3. Talk to the stub with **raw GDB-protocol packets**, not the gdb client
   (gdb misreads registers/memory because the stub's `g` reply is truncated).
4. The stub accepts **exactly one connection** and the listener dies when the
   connection drops. Recovery = relaunch the GAME (not Dolphin). NEVER kill
   the client, never detach.
5. Loading a savestate **kills the stub's timing event** — after a savestate,
   the 0x03 interrupt and while-running command polling are dead. Breakpoint
   hits still work (they go through the CPU thread, not the timing event).
6. Interpreter + debugging = slow (~20 fps). A level load takes minutes of
   real time. Breakpoints WILL fire if the game actually executes the address.

## Environment (this machine)

- Flatpak Dolphin: `flatpak run --share=network org.DolphinEmu.dolphin-emu -d`
  (`--share=network` exposes the GDB port to the host).
- Flatpak pins Dolphin commit `6094cfcf7b8fba733b3116fdf3414d51c1c0e4a4`
  (June 2026, v2606). Its `GDBStub.cpp` is byte-identical to master.
- Config dir: `~/.var/app/org.DolphinEmu.dolphin-emu/config/dolphin-emu/`
- GDB stub: `[General] GDBPort = 2159` in `Dolphin.ini`.
- Game: Nicktoons Unite! (GNOE78), savestates `.s01` (start of DP1 loading),
  `.s02` (in-level).
- The NixOS `dolphin-emu` package does NOT compile with `-DGDBSTUB=ON`
  (CMake flag defaults off; Nix never enables it). Flatpak does.

## The one setting: DebugModeEnabled

`Config::IsDebuggingEnabled()` gates the interpreter's entire breakpoint path:

```cpp
// Interpreter.cpp Interpreter::Run()
if (Config::IsDebuggingEnabled()) {
  while (!m_end_block) {
    if (power_pc.CheckAndHandleBreakPoints())   // breakpoints checked HERE
      return;
    cycles += SingleStepInner();
  }
} else {
  // "fast" path — NO breakpoint checks at all. The game runs forever,
  // breakpoints silently never fire.
}
```

Setting: `[Interface] DebugModeEnabled = True` in Dolphin.ini
(`Config::MAIN_ENABLE_DEBUGGING`). Also disabled when RetroAchievements
Hardcore mode is active.

Symptom when missing: `continue` never stops at the breakpoint, and the 0x03
interrupt never gets a reply.

## Why the gdb client lies to you

The stub's `ReadRegisters` (`g` packet) sends only the 32 GPRs, but gdb's
powerpc register map expects ~140 registers. gdb pads/misreads the reply, so
**every register gdb displays is garbage** (e.g. it showed `pc=0x68a10380`
when the real pc was `0x8003A168`). Memory reads are fine; individual `p`
packets are fine; the `g` packet is the trap.

Use `gdbraw.py` instead (raw `$cmd#chk` packets):
- `p<regid>` reads one register (reg 64 = pc, 67 = lr, 1 = r1, 3 = r3, ...)
- `m<addr>,<len>` reads memory (max ~0x1300 per packet)
- `Z0,<addr>,4` set breakpoint / `Z3,<addr>,<len>` read-watchpoint (memcheck)
- `c` continue (no reply until the next stop)
- `0x03` interrupt byte (only works while the timing event is alive)

## Connection lifecycle (the dance, explained)

From `GDBStub.cpp InitGeneric`: the stub `listen(1)`s, `accept()`s ONE
client, then closes the listener. `Deinit()` (triggered by a failed recv on
the client socket) shuts down the accepted socket.

- Connect → game pauses (the CPU thread goes to Stepping and hands control
  to the stub's `ProcessCommands(true)` loop).
- `c` → game runs. `s_has_control = false`.
- Breakpoint hit → `CPU::Break()` + `GDBStub::TakeControl()` (control back)
  → the CPU thread's Stepping case sends `SendSignal(Sigtrap)` + re-enters
  `ProcessCommands(true)`. This is the ONLY reliable stop path.
- Client disconnects/kills → stub `recv` fails → `Deinit` → listener gone.
  The port is dead until the game is relaunched (stub re-inits on game
  start). **Do not kill the client. Do not detach.**

## The savestate timing-event bug

The stub polls while the game runs via a self-rescheduling CoreTiming event
(`GDBStubUpdate`, every 100000 cycles → `UpdateCallback` → `ProcessCommands`).
Loading a savestate restores the CoreTiming queue from the save — which does
not contain this event — so **after any savestate load, while-running command
polling and the 0x03 interrupt are dead** (the byte sits in the socket recv
buffer, Recv-Q=1, forever unread).

Breakpoint hits are NOT affected: they stop the CPU and go through the CPU
thread's Stepping command loop, not the timing event. So the working pattern
after a savestate is: breakpoints + continue only. No interrupts.

## Working recipes

### Persistent raw session

```
flatpak run --share=network org.DolphinEmu.dolphin-emu -d   # start game
./rawdrive.sh        # holds one raw-protocol connection via a FIFO
./rawsend.sh "query" # or: reg 3 / mem 0x805E3940 0x100 / bp 0x800217bc / cont
tail -f raw.log
```

`rawdrive.sh` runs `python3 -u gdbraw.py repl < fifo` — the `-u` matters
(block-buffered stdout would swallow replies). Kill nothing; just let it sit.

### Dispatcher scan (find collision processing)

`scan2.py` connects, breaks at the resource dispatcher `0x800217bc`, and on
every hit dumps the dispatch record (`r3` + fields `c14/c18/c1c/c20`) and
scans the staging buffer at `c18` for the collision record block. When found
it arms a `Z3` read-watchpoint and holds — the next non-dispatcher stop is
the code that reads the collision bytes.

Run it, then load `.s01` in Dolphin (the level load dispatches the mesh
TRBs). The title screen dispatches boot resources only (code overlays,
animation TRBs) — mesh/collision TRBs only load with the level.

### Known addresses / data (from the collision investigation)

- Dispatcher (resource chunk dispatch): `0x800217bc`. `r3` = dispatch record:
  `+0x08` type, `+0x14` c14, `+0x18` c18 = staging buffer ptr, `+0x1c` c1c,
  `+0x20` c20. Type 1 = common case.
- Mesh TRBs in the staging buffer start `"TSFB"` + BE size + `"FBRTXRDH"`.
- Collision block format: **UNKNOWN**. The 4-byte `(flag, x, y, z)` s8
  reading from this investigation and the later 3-byte u8-triple reading
  (docs/trb-collision-test.md) are both unverified structural hypotheses —
  the collision mesh format has not been established (see
  docs/collision-status.md).
- No dequantization/transform was ever confirmed in code. Locating the
  code that actually consumes these bytes (and its bbox source, if any) is
  the open goal.
- Staging buffers are transient: resources are read in, processed, and the
  buffer is reused. The collision bytes only exist in memory during the mesh
  TRB's processing window — which is exactly why the watchpoint must be
  armed during the dispatch hit.

## Stub protocol notes (GDBStub.cpp)

- Ack `+` after every packet; reply is `$... #chk`; `0x03` is the interrupt.
- `qSupported` → `swbreak+;hwbreak+`. `qHostInfo` → `endian:big;ptrsize:4`.
- Breakpoints/memchecks are host-side; they survive savestate loads.
- `Z3` = read breakpoint (TMemCheck `is_break_on_read`). Memchecks fire via
  the interpreter's `EXCEPTION_FAKE_MEMCHECK_HIT` path (needs
  DebugModeEnabled too).
- `ReadMemory` is capped at ~0x1382 bytes (reply buffer 10000 minus 4).
- Registers: 0-31 GPR, 64 pc, 65 msr, 66 cr, 67 lr, 68 ctr, 69 xer,
  70 fpscr, 71-86 sr, 87 pvr, 104 sdr, 105 asr (64-bit), 106 dar, 107 dsisr,
  108-111 sprg0-3, 112 srr0, 113 srr1, 116 dec.

## Files

- `gdbraw.py` — raw GDB-protocol client (single-shot + `repl` modes)
- `scan.py` — v1 dispatcher scanner (boot-load log; kept as reference)
- `scan2.py` — v2: finds collision block + arms read-watchpoint, holds
- `rawdrive.sh` / `rawsend.sh` — persistent session driver (FIFO)
