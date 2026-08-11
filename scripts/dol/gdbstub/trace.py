#!/usr/bin/env python3
"""Auto-trace driver for the grilled-dolphin control server.

Rides the level load: waits for BP stops, logs dispatch records / read
completions, dumps the staging buffer when a mesh TRB appears, and computes
watchpoint candidates. Usage: trace.py [max_stops] [timeout_per_stop]
"""
import json, socket, struct, sys, time, os

HOST, PORT = "127.0.0.1", 2200
DUMPDIR = "/tmp/trb_dumps"
os.makedirs(DUMPDIR, exist_ok=True)

def call(method, params=None):
    req = {"id": 1, "method": method, "params": params or []}
    s = socket.create_connection((HOST, PORT), timeout=60)
    s.sendall((json.dumps(req) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    s.close()
    resp = json.loads(buf.decode())
    if "error" in resp:
        raise RuntimeError(f"{method}: {resp['error']}")
    return resp.get("result")

def rbytes(addr, n):
    return bytes.fromhex(call("memory.read_bytes", [addr, n]))

def w32(d, o):
    return struct.unpack(">I", d[o:o+4])[0]

def dump_regs():
    r = call("ppc.registers")
    g = r["gpr"]
    return r, g

BP_DISPATCH = 0x800217BC
BP_COMPLETE = 0x80021AFC
BP_PUMP     = 0x800214D4
BP_POLL     = 0x8002289C

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def handle_stop():
    r, g = dump_regs()
    pc = r["pc"]
    r3 = g[3]
    if pc == BP_DISPATCH:
        # dispatch record at r3
        d = rbytes(r3, 0x40)
        typ = w32(d, 0x08)
        c10, c14, c18, c1c, c20 = w32(d,0x10), w32(d,0x14), w32(d,0x18), w32(d,0x1c), w32(d,0x20)
        c28 = w32(d, 0x28)
        c38 = w32(d, 0x38)
        obj = w32(d, 0x00)
        obuf = osize = 0
        if 0x80000000 <= obj <= 0x81800000:
            try:
                od = rbytes(obj, 0x58)
                obuf = w32(od, 0x18)
                osize = w32(od, 0x34)
            except Exception:
                pass
        tag = ""
        if 0x35083E64 <= c10 < 0x35083E64 + 0x40000 or 0x350ED898 <= c10 < 0x350ED898 + 0x20000 or 0x350D3398 <= c10 < 0x350D3398 + 0x20000:
            tag = " <== MESH TRB READ"
        elif typ == 1 and c1c > 0x10000:
            tag = " <== BIG READ"
        # peek staging buffer magic+size
        st = ""
        if 0x80000000 <= c18 <= 0x81800000:
            try:
                sh = rbytes(c18, 8)
                if sh[:4] == b"TSFB":
                    st = " bufsize=%x" % w32(sh, 4)
            except Exception:
                pass
        log(f"DISPATCH rec={r3:08x} type={typ} c10={c10:08x} c14={c14:08x} c18={c18:08x} len={c1c} c20={c20} cb={c28:08x} c38={c38:08x} obj={obj:08x} obuf={obuf:08x} osize={osize}{st}{tag}")
        if tag.startswith(" <== MESH"):
            open("/tmp/mesh_trb_found", "w").write("%08x %08x %08x %08x\n" % (c10, obuf, osize, r3))
            # AUTO-ARM: read-watchpoint on the whole staged mesh TRB
            if 0x80000000 <= c18 <= 0x81800000:
                try:
                    call("memchecks.clear_all")
                    call("memchecks.set", [c18, 0x16AA4, {"read": True, "write": False}])
                    log("  *** MEMCHECK ARMED on mesh TRB staging %08x len %x" % (c18, 0x16AA4))
                except Exception as e:
                    log("  arm failed: %s" % e)
        return None
    if pc == BP_COMPLETE:
        # read completion: r3 = status bits
        # current record ptr at r13-0x5E78
        r13 = g[13]
        recp = (r13 - 0x5E78) & 0xFFFFFFFF
        d = rbytes(recp, 0x30)
        typ = w32(d, 0x08)
        c18 = w32(d, 0x18)
        c20 = w32(d, 0x20)
        c14 = w32(d, 0x14)
        c1c = w32(d, 0x1c)
        log(f"READ COMPLETE r3={r3:08x} lr={r['lr']:08x} rec c18={c18:08x} len={c1c}")
        # check staging buffer for TSFB mesh TRB
        if c18 >= 0x80000000 and c1c > 0x10000:
            try:
                hdr = rbytes(c18, 0x20)
            except Exception:
                return None
            tag = hdr[:4].decode('latin1', 'replace')
            if hdr[:4] == b"TSFB":
                sz = w32(hdr, 0x10)
                log(f"  *** TSFB mesh TRB at c18={c18:08x} size={sz} len={c1c}")
                fn = os.path.join(DUMPDIR, f"trb_{int(time.time())}.bin")
                with open(fn, "wb") as f:
                    n = min(sz, 0x80000)
                    for o in range(0, n, 0x10000):
                        f.write(rbytes(c18 + o, min(0x10000, n - o)))
                log(f"  dumped {n} bytes -> {fn}")
                return fn
            else:
                log(f"  buffer magic={tag!r} (not TSFB)")
        return None
    if pc == BP_PUMP:
        log(f"PUMP r3={r3:08x}")
        return None
    if pc == BP_POLL:
        log(f"POLL r3={r3:08x}")
        return None
    log(f"STOP pc={pc:08x} lr={r['lr']:08x} r3={r3:08x}")
    return None

def main():
    max_stops = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 15000
    stops = 0
    last_dump = None
    while stops < max_stops:
        st = call("debug.wait_stop", [timeout])
        if not st.get("paused", False):
            log("NO STOP (timeout) - load quiet")
            break
        stops += 1
        try:
            last_dump = handle_stop() or last_dump
        except Exception as e:
            log(f"ERR in handle_stop: {e}")
        call("emulation.resume")
        # brief settle so the CPU actually runs before next wait_stop
        time.sleep(0.05)
    log(f"done: {stops} stops")

if __name__ == "__main__":
    main()
