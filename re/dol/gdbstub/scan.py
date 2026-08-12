#!/usr/bin/env python3
"""
Autonomous dispatcher scanner: continues the game, catches 0x800217bc hits,
dumps dispatch records, classifies collision vs other chunks, keeps going
until collision data is found, then stops (game paused).
"""
import socket
import sys
import time

HOST = "127.0.0.1"
PORT = 2159
BP = 0x800217BC
MAX_HITS = 200


class Stub:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT), timeout=15)
        self.s.settimeout(30)

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
        self.s.recv(1)  # ack

    def wait_stop(self, timeout=300):
        """Wait for a stop reply packet. Returns raw reply bytes or None."""
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
            self.s.settimeout(30)


def classify(data: bytes, chunk_id: int, ctype: int):
    """Classify data: collision-like? Returns (bool, description)."""
    if len(data) < 12:
        return False, f"short({len(data)})"
    n = min(len(data) // 4, 0x80)
    flags = set()
    xv, yv, zv = set(), set(), set()
    for i in range(n * 4 - 3):
        b0, b1, b2, b3 = data[i], data[i + 1], data[i + 2], data[i + 3]
        flags.add(b0)
        xv.add(b1)
        yv.add(b2)
        zv.add(b3)
    xr = max(xv) - min(xv) if xv else 0
    yr = max(yv) - min(yv) if yv else 0
    zr = max(zv) - min(zv) if zv else 0
    # collision signature: byte1/byte3 wide, byte2 narrow, flags in {0,1,2,3,255}
    flag_ok = flags <= {0, 1, 2, 3, 255}
    wide = xr > 40 and zr > 40
    narrow = yr <= 5
    printable = sum(1 for b in data[:64] if 32 <= b < 127) / min(len(data), 64) > 0.8
    is_col = flag_ok and wide and narrow and not printable
    desc = (f"flags={sorted(flags)} xr={xr} yr={yr} zr={zr} printable={printable:.2f}")
    return is_col, desc


def main():
    stub = Stub()
    print(f"CONNECTED {time.strftime('%H:%M:%S')}")
    # ensure breakpoint
    r = stub.cmd(f"Z0,{BP:x},4")
    print(f"BP set: {r}")

    hits = []
    for i in range(MAX_HITS):
        stub.continue_run()
        stop = stub.wait_stop(timeout=600)
        if stop is None:
            print(f"[{i}] NO STOP in 600s — game not loading?")
            break
        # parse stop reply: Tss<rid>:<val>;... first reg is pc(64)
        try:
            sig = int(stop[1:3], 16)
        except Exception:
            sig = -1
        # read r3 = dispatch record
        r3 = stub.read_reg(3)
        rec = stub.read_mem(r3, 0x30) if r3 else b""
        ctype = int.from_bytes(rec[8:12], "big") if len(rec) >= 12 else -1
        c10 = int.from_bytes(rec[16:20], "big") if len(rec) >= 20 else 0
        c14 = int.from_bytes(rec[20:24], "big") if len(rec) >= 24 else 0
        c18 = int.from_bytes(rec[24:28], "big") if len(rec) >= 28 else 0
        c1c = int.from_bytes(rec[28:32], "big") if len(rec) >= 32 else 0
        c20 = int.from_bytes(rec[32:36], "big") if len(rec) >= 36 else 0

        data = stub.read_mem(c18, 0x200) if c18 else b""
        is_col, desc = classify(data, i, ctype)
        tag = "*** COLLISION ***" if is_col else ""
        print(f"[{i}] sig={sig} r3={r3:08X} type={ctype} c10={c10:08X} c14={c14:08X} "
              f"c18={c18:08X} c1c={c1c:08X} c20={c20:08X} {desc} {tag}")
        sys.stdout.flush()
        if data:
            preview = data[:24].hex(" ")
            print(f"     data: {preview}")
        hits.append((i, ctype, c18, is_col))
        if is_col:
            print(f"COLLISION FOUND at hit {i} — game paused, investigating")
            break
        if sig == 0x0F:  # sigterm — maybe savestate/other stop
            pass

    print(f"DONE — {len(hits)} hits")
    cols = [h for h in hits if h[3]]
    print(f"collision chunks: {len(cols)}")


if __name__ == "__main__":
    main()
