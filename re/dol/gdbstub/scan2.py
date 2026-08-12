#!/usr/bin/env python3
"""
FINAL scanner: catch mesh TRB dispatches during level load, find the
collision record block in the staging buffer, set a read-watchpoint on it,
and catch the game reading the collision bytes (the code that consumes the
collision block — format unknown, see docs/collision-status.md).

Holds the connection open forever after finding the target. NEVER exits on
its own (that kills the stub).
"""
import socket
import sys
import time

HOST = "127.0.0.1"
PORT = 2159
BP = 0x800217BC
MAX_HITS = 10000


class Stub:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT), timeout=15)
        self.s.settimeout(60)

    def chk(self, c: bytes) -> bytes:
        return f"{sum(c) & 0xFF:02x}".encode()

    def cmd(self, c: str) -> bytes:
        c = c.encode()
        self.s.sendall(b"$" + c + b"#" + self.chk(c))
        ack = self.s.recv(1)
        if ack != b"+":
            return b""
        buf = b""
        while True:
            ch = self.s.recv(1)
            if ch == b"$":
                buf = b""
            elif ch == b"#":
                self.s.recv(2)
                return buf
            else:
                buf += ch

    def read_reg(self, rid: int) -> int:
        r = self.cmd(f"p{rid:02x}")
        return int(r, 16) if r else 0

    def read_mem(self, addr: int, length: int) -> bytes:
        if not (0x80000000 <= addr <= 0x81800000):
            return b""
        r = self.cmd(f"m{addr:x},{length:x}")
        if not r or r in (b"E00", b"E01"):
            return b""
        try:
            return bytes.fromhex(r.decode())
        except ValueError:
            return b""

    def continue_run(self):
        self.s.sendall(b"$c#63")
        self.s.recv(1)

    def wait_stop(self, timeout=900):
        self.s.settimeout(timeout)
        try:
            while True:
                ch = self.s.recv(1)
                if ch == b"$":
                    buf = b""
                    while True:
                        ch2 = self.s.recv(1)
                        if ch2 == b"#":
                            self.s.recv(2)
                            return buf
                        buf += ch2
        except socket.timeout:
            return None
        finally:
            self.s.settimeout(60)


def find_collision(data: bytes, base_addr: int):
    """Scan a buffer for the collision record block.
    Records: (flag, x, y, z) s8, 4 bytes each.
    flag in {0,1,2,255} mostly; x,z wide; y NARROW per footprint.
    Returns (addr, len) of the best run or None."""
    n = len(data) - 3
    best = None
    i = 0
    while i < n - 4:
        # candidate start: record with flag in {0,1,2,255} and x/z nonzero spread
        b0, b1, b2, b3 = data[i], data[i+1], data[i+2], data[i+3]
        if b0 not in (0, 1, 2, 255):
            i += 4
            continue
        # gather a run
        j = i
        flags = set()
        ys = set()
        while j < n - 3:
            f, x, y, z = data[j], data[j+1], data[j+2], data[j+3]
            if f not in (0, 1, 2, 255):
                break
            flags.add(f)
            ys.add(y)
            if len(ys) > 6:
                break
            j += 4
        runlen = (j - i) // 4
        if runlen >= 8 and len(flags) >= 2:
            # verify x/z spread in the run
            seg = data[i:j]
            xs = set(seg[k+1] for k in range(0, len(seg), 4))
            zs = set(seg[k+3] for k in range(0, len(seg), 4))
            x_wide = (max(xs) - min(xs)) > 30
            z_wide = (max(zs) - min(zs)) > 30
            if x_wide and z_wide:
                if best is None or runlen > best[2]:
                    best = (base_addr + i, j - i, runlen, sorted(flags), sorted(ys))
        i = j + 4
    return best


def main():
    stub = Stub()
    print(f"CONNECTED {time.strftime('%H:%M:%S')}")
    r = stub.cmd(f"Z0,{BP:x},4")
    print(f"BP set: {r}")

    watched = False
    for i in range(MAX_HITS):
        stub.continue_run()
        stop = stub.wait_stop()
        if stop is None:
            print(f"[{i}] NO STOP in 900s — game idle? holding connection")
            break
        try:
            sig = int(stop[1:3], 16)
        except Exception:
            sig = -1
        r3 = stub.read_reg(3)
        rec = stub.read_mem(r3, 0x30) if r3 else b""
        ctype = int.from_bytes(rec[8:12], "big") if len(rec) >= 12 else -1
        c14 = int.from_bytes(rec[20:24], "big") if len(rec) >= 24 else 0
        c18 = int.from_bytes(rec[24:28], "big") if len(rec) >= 28 else 0
        c1c = int.from_bytes(rec[28:32], "big") if len(rec) >= 32 else 0
        c20 = int.from_bytes(rec[32:36], "big") if len(rec) >= 36 else 0

        # read up to 0x5000 of the staging buffer (chunked, max 0x1300/packet)
        data = b""
        if c18 and 0x80000000 <= c18 <= 0x81800000:
            for off in range(0, 0x5000, 0x1300):
                chunk = stub.read_mem(c18 + off, 0x1300)
                if not chunk:
                    break
                data += chunk

        tag = ""
        if data[:4] == b"TSFB":
            tag = f"TSFB sz=0x{int.from_bytes(data[4:8],'big'):X}"
        hit = find_collision(data, c18) if c18 else None
        if hit:
            addr, ln, runlen, flags, ys = hit
            tag += f" *** COLLISION @ 0x{addr:08X} len={ln} run={runlen} flags={flags} y={ys}"
        print(f"[{i}] sig={sig} r3={r3:08X} type={ctype} c14={c14:08X} c18={c18:08X} "
              f"c1c={c1c:08X} c20={c20:08X} {tag}")
        sys.stdout.flush()

        if hit and not watched:
            addr, ln, runlen, flags, ys = hit
            # set read-watchpoint (Z3) on the collision records
            wr = stub.cmd(f"Z3,{addr:x},{ln:x}")
            print(f"  >> WATCHPOINT on 0x{addr:08X} len={ln}: {wr}")
            watched = True
            # snapshot the records for reference
            snap = stub.read_mem(addr, min(ln, 0x80))
            print(f"  >> records: {snap.hex(' ') if snap else 'ERR'}")
            continue

        if watched:
            # could be the dispatcher BP again, or the watchpoint firing
            pc = stub.read_reg(64)
            if pc == BP:
                print(f"  >> dispatcher BP again (pc={pc:08X}) — continuing")
                sys.stdout.flush()
                continue
            print(f"  >> *** WATCHPOINT STOP *** pc={pc:08X}")
            code = stub.read_mem(pc & ~3, 0x30)
            print(f"  >> code around pc: {code.hex(' ') if code else 'ERR'}")
            # LR + nearby regs — the conversion call context
            lr = stub.read_reg(67)
            r4 = stub.read_reg(4)
            r5 = stub.read_reg(5)
            r6 = stub.read_reg(6)
            print(f"  >> r3={r3:08X} r4={r4:08X} r5={r5:08X} r6={r6:08X} lr={lr:08X}")
            print("  >> HOLDING CONNECTION — game paused at collision-byte read")
            sys.stdout.flush()
            while True:
                time.sleep(3600)

    print(f"DONE {i} hits — holding connection")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
