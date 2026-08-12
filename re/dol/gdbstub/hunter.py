#!/usr/bin/env python3
"""Lean mesh-TRB hunter: dispatcher BP only, minimal per-stop work, auto-arms
a read-watchpoint on the staged mesh TRB, then captures the reader."""
import json, socket, struct, sys, time, os

HOST, PORT = "127.0.0.1", 2200
MESH_RANGES = [(0x35083E64, 0x40000), (0x350D3398, 0x20000), (0x350ED898, 0x20000)]
BP_DISPATCH = 0x800217BC

def call(m, p=None):
    s = socket.create_connection((HOST, PORT), timeout=30)
    s.sendall((json.dumps({"id": 1, "method": m, "params": p or []}) + "\n").encode())
    b = b""
    while b"\n" not in b:
        c = s.recv(65536)
        if not c:
            break
        b += c
    s.close()
    r = json.loads(b.decode())
    if "error" in r:
        raise RuntimeError(f"{m}: {r['error']}")
    return r.get("result")

def rbytes(addr, n):
    return bytes.fromhex(call("memory.read_bytes", [addr, n]))

def w32(d, o):
    return struct.unpack(">I", d[o:o+4])[0]

def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "hunt"
    if mode == "reset":
        call("breakpoints.clear_all")
        call("memchecks.clear_all")
        call("breakpoints.set", [BP_DISPATCH])
        log("reset: dispatcher BP only, memchecks cleared")
        return
    if mode == "armed":
        # we're past arming; wait for the memcheck hit and capture the reader
        while True:
            st = call("debug.wait_stop", [60000])
            if not st.get("paused"):
                log("NO STOP (timeout)")
                continue
            pc = st["pc"]
            if pc == BP_DISPATCH:
                # another dispatch (mesh sectors) - skip fast
                call("emulation.resume")
                continue
            r = call("ppc.registers")
            g = r["gpr"]
            log(f"*** READER STOP pc={pc:08x} lr={r['lr']:08x} r3={g[3]:08x} r4={g[4]:08x} r5={g[5]:08x}")
            try:
                mc = call("memchecks.list")
                for e in mc:
                    if e.get("num_hits", 0):
                        log(f"  memcheck hit: {e['start']:08x}-{e['end']:08x} hits={e['num_hits']}")
            except Exception:
                pass
            open("/tmp/reader_caught", "w").write("%08x\n" % pc)
            call("emulation.resume")
            time.sleep(1)
            return
    # hunt mode: fast loop over dispatcher stops
    stops = 0
    while True:
        st = call("debug.wait_stop", [20000])
        if not st.get("paused"):
            log("NO STOP (timeout) - load quiet, waiting for next dispatch...")
            continue
        pc = st["pc"]
        if pc != BP_DISPATCH:
            # stray stop (pump etc.) - resume
            call("emulation.resume")
            continue
        stops += 1
        r = call("ppc.registers")
        g = r["gpr"]
        rec = g[3]
        d = rbytes(rec, 0x1C)
        typ = w32(d, 0x08)
        c10 = w32(d, 0x10)
        c18 = w32(d, 0x18)
        in_mesh = any(lo <= c10 < lo + ln for lo, ln in MESH_RANGES)
        if not in_mesh and typ == 1 and c18:
            # signature probe: any TSFB whose first chunk (at +0x34) is LDMT = mesh TRB
            try:
                sig = rbytes(c18 + 0x30, 8)
                if sig[4:8] == b"LDMT" and sig[:4] == b"TSFB":
                    in_mesh = True
            except Exception:
                pass
        if stops % 5 == 0 or in_mesh:
            log(f"stops={stops} type={typ} c10={c10:08x} c18={c18:08x}")
        if in_mesh:
            log(f"=== MESH TRB READ: c10={c10:08x} staging={c18:08x} ===")
            # dump the staged file
            try:
                h = rbytes(c18, 0x20)
                sz = w32(h, 4) if h[:4] == b"TSFB" else 0
                log(f"  staged magic={h[:4]!r} size={sz:x}")
            except Exception as e:
                log(f"  staged read failed: {e}")
                sz = 0x16AA4
            call("memchecks.clear_all")
            call("memchecks.set", [c18, sz or 0x16AA4, {"read": True, "write": False}])
            log(f"  *** READ-ONLY MEMCHECK ARMED: {c18:08x}+{sz:x}")
            open("/tmp/mesh_trb_found", "w").write("%08x %08x %08x\n" % (c10, c18, sz))
            call("emulation.resume")
            main("armed")  # switch to armed capture
            return
        call("emulation.resume")

if __name__ == "__main__":
    main()
