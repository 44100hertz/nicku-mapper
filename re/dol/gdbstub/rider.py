#!/usr/bin/env python3
"""Manual dispatcher rider: clear-BP -> resume -> rearm -> wait for stop.
Logs every dispatch (type, disc offset, len, staging) and auto-arms a
read-memcheck when the staged buffer carries a TSFB/LDMT mesh signature.
Capture the reader on the memcheck hit (pc/lr/regs + memcheck details)."""
import json, socket, struct, sys, time

HOST, PORT = "127.0.0.1", 2200
BP = 0x800217BC
MESH_RANGES = [(0x35083E64, 0x40000), (0x350D3398, 0x20000), (0x350ED898, 0x20000)]

def call(m, p=None, timeout=30):
    s = socket.create_connection((HOST, PORT), timeout=timeout)
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

def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def poll_pause(timeout_s):
    """Poll until the core reports paused (or timeout)."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            st = call("bridge.status", timeout=10)
            if st.get("state") == "paused":
                return st
        except Exception:
            pass
        time.sleep(1.5)
    return None

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "ride"
    if mode == "arm":
        # arm the BP and wait for the first dispatch stop
        call("breakpoints.clear_all"); call("memchecks.clear_all")
        call("breakpoints.set", [BP])
        log("BP armed, waiting for dispatch...")
        st = poll_pause(120)
        return st is not None
    if mode == "capture":
        # we're paused at the memcheck; capture the reader
        r = call("ppc.registers")
        g = r["gpr"]
        log(f"*** READER pc={r['pc']:08x} lr={r['lr']:08x} r3={g[3]:08x} r4={g[4]:08x} r5={g[5]:08x}")
        try:
            for e in call("memchecks.list"):
                if e.get("num_hits", 0):
                    log(f"  memcheck hit: {e['start']:08x}-{e['end']:08x} hits={e['num_hits']}")
        except Exception:
            pass
        open("/tmp/reader_caught", "w").write("%08x\n" % r["pc"])
        return True

    # ride: infinite loop
    stops = 0
    while True:
        st = poll_pause(90)
        if st is None:
            log("no stop in 90s - game quiet; rearming")
            call("breakpoints.set", [BP])
            continue
        r = call("ppc.registers")
        pc = r["pc"]
        if pc != BP:
            log(f"stray stop pc={pc:08x}; resume")
            call("breakpoints.clear_all")
            call("emulation.resume")
            continue
        stops += 1
        g = r["gpr"]
        rec = g[3]
        d = bytes.fromhex(call("memory.read_bytes", [rec, 0x1C]))
        typ = struct.unpack(">I", d[8:12])[0]
        c10 = struct.unpack(">I", d[0x10:0x14])[0]
        c14 = struct.unpack(">I", d[0x14:0x18])[0]
        c18 = struct.unpack(">I", d[0x18:0x1C])[0]
        sig = b""
        if typ == 1 and 0x80000000 <= c18 < 0x81800000:
            try:
                sig = bytes.fromhex(call("memory.read_bytes", [c18 + 0x30, 8]))
            except Exception:
                pass
        is_mesh = any(lo <= c10 < lo + ln for lo, ln in MESH_RANGES) or \
                  (sig[:4] == b"TSFB" and sig[4:8] == b"LDMT")
        log(f"stops={stops} type={typ} c10={c10:08x} len={c14:x} c18={c18:08x} sig={sig!r}" + ("  <<< MESH" if is_mesh else ""))
        # clear the BP so resume doesn't self-loop, then resume
        call("breakpoints.clear_all")
        if is_mesh:
            sz = c14 if c14 and c14 < 0x100000 else 0x16AA4
            call("memchecks.set", [c18, sz, {"read": True, "write": False}])
            log(f"*** MESH TRB READ c10={c10:08x} staged={c18:08x}+{sz:x}; memcheck armed, resuming")
            open("/tmp/mesh_trb_found", "w").write(f"{c10:08x} {c18:08x} {sz:x}\n")
            call("emulation.resume")
            st = poll_pause(30)
            if st:
                main("capture")
            return
        call("emulation.resume")
        # rearm the BP quickly
        call("breakpoints.set", [BP])

if __name__ == "__main__":
    main()
