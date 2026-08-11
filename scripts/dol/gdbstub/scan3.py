#!/usr/bin/env python3
"""
scan3.py — persistent collision-loader hunter (Dolphin GDB stub).

Holds ONE connection forever. Breaks at the resource dispatcher, catches the
mesh-TRB dispatch for a level part, parses the staging buffer with the
verified TRB layout, arms read-watchpoints on the collision candidates
(mesh-record table, the 0x38AC-style section list, C-block trailing data of
the largest meshes), and logs every subsequent stop (the reader code) with
full context. Command channel: UNIX socket /tmp/scan3.sock (see scan3cmd.py).

NEVER exits on its own (that kills the stub). Logs to scan3.log.
"""
import os
import select
import socket
import struct
import sys
import time

HOST = "127.0.0.1"
PORT = 2159
BP_DISPATCH = 0x800217BC
MAX_STOPS = 80
STOP_TIMEOUT = 240
DUMP_DIR = "/tmp/trb_dumps"
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan3.log")
SOCK = "/tmp/scan3.sock"


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


class Stub:
    def __init__(self, retry=600):
        # Keep retrying until the stub accepts us. A single failed connect
        # must never kill the driver (one-shot connection rule).
        deadline = time.time() + retry
        last = None
        while time.time() < deadline:
            try:
                self.s = socket.create_connection((HOST, PORT), timeout=5)
                self.s.settimeout(60)
                log("CONNECTED to stub (game paused on connect)")
                return
            except OSError as e:
                last = e
                log(f"connect retry: {e}")
                time.sleep(2)
        raise last

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
        out = b""
        while length > 0:
            n = min(length, 0x1300)
            r = self.cmd(f"m{addr:x},{n:x}")
            if not r or r in (b"E00", b"E01"):
                break
            try:
                out += bytes.fromhex(r.decode())
            except ValueError:
                break
            addr += n
            length -= n
        return out

    def bp(self, addr: int, on: bool = True) -> bool:
        r = self.cmd(f"Z{0 if on else 1}0,{addr:x},4")
        return r == b"OK"

    def watch(self, addr: int, length: int, on: bool = True) -> bool:
        r = self.cmd(f"Z{3 if on else 4},{addr:x},{length:x}")
        return r == b"OK"

    def continue_run(self):
        self.s.sendall(b"$c#63")
        self.s.recv(1)

    def wait_stop(self, timeout=STOP_TIMEOUT):
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


# ---------------- TRB parsing (embedded; matches trb_mesh.py) ----------------

def parse_trb(data: bytes):
    out = {"sect": None, "sizes": [], "symbs": {}, "relc_offs": set()}
    if len(data) < 0x30 or data[:4] != b"TSFB":
        return None
    hdrx_size = struct.unpack_from(">I", data, 0x10)[0]
    n = struct.unpack_from(">I", data, 0x18)[0]
    if hdrx_size <= 0x20 or n > 0x400:
        return None
    sizes = [struct.unpack_from(">I", data, 0x20 + 16 * i)[0] for i in range(n)]
    sect = hdrx_size + 20 + 8
    out["sect"] = sect
    out["sizes"] = sizes
    q = sect + sum(sizes)
    while q + 8 <= len(data):
        tag = data[q:q + 4]
        sz = struct.unpack_from(">I", data, q + 4)[0]
        if tag == b"CLER":
            for i in range(sz // 8):
                off, tgt = struct.unpack_from(">II", data, q + 8 + 8 * i)
                out["relc_offs"].add(off)
        elif tag == b"BMYS":
            s = data[q + 8:q + 8 + sz]
            cnt = struct.unpack_from(">I", s, 0)[0]
            names = s[4 + cnt * 12:]
            for i in range(cnt):
                e = s[4 + i * 12:4 + i * 12 + 12]
                no = struct.unpack_from(">H", e, 2)[0]
                nm = names[no:].split(b"\x00")[0].decode("latin1")
                out["symbs"][nm] = struct.unpack_from(">I", e, 8)[0]
        q += 4
        if q + 8 > len(data):
            break
    return out


FLAG_RECW = {
    0x06020202: 3, 0x06020203: 4, 0x06030202: 4, 0x06030203: 5,
    0x06020201: 6, 0x06020101: 7, 0x06030101: 8,
}


def plan_watchpoints(data: bytes, c18: int):
    t = parse_trb(data)
    if not t:
        return []
    sect, sizes = t["sect"], t["sizes"]
    sect_ram = c18 + sect
    recs = {}
    for nm, off in t["symbs"].items():
        if nm.startswith("W0C0M"):
            try:
                recs[int(nm[5:])] = off
            except ValueError:
                pass
    n_mesh = len(recs)
    log(f"PLAN: sect_ram=0x{sect_ram:08X} sizes0=0x{sizes[0]:X} meshes={n_mesh}")
    out = []
    if not recs:
        return out
    mesh0 = min(recs.values())
    T = None
    for off in range(max(0, mesh0 - 0x1000), mesh0 - 0x10):
        if struct.unpack_from(">I", data, sect + off)[0] != n_mesh:
            continue
        x = struct.unpack_from(">I", data, sect + off + 4)[0]
        y = struct.unpack_from(">I", data, sect + off + 8)[0]
        if x == off + 0xC and y == off + 0xC + n_mesh * 4:
            T = off
            break
    if T is not None:
        list_off = struct.unpack_from(">I", data, sect + T + 8)[0]
        out.append((sect_ram + list_off, min(mesh0 - list_off, 0x400), "SECT list"))
        out.append((sect_ram + T, min(mesh0 - T, 0x800), "mesh table"))
        log(f"PLAN: table T=0x{T:X} list=0x{list_off:X} region 0x{list_off:X}..0x{mesh0:X}")
    else:
        log("PLAN: mesh table not found by pattern; watching pre-mesh0 region")
        out.append((sect_ram + mesh0 - 0x400, min(0x400, mesh0), "pre-mesh0 guess"))
    big = sorted(recs.items(), key=lambda kv: -struct.unpack_from(
        ">I", data, sect + kv[1] + 0x24)[0])[:6]
    for k, off in big:
        C = struct.unpack_from(">I", data, sect + off + 0x20)[0]
        D = struct.unpack_from(">I", data, sect + off + 0x24)[0]
        F = struct.unpack_from(">I", data, sect + off + 0x2C)[0]
        flag = struct.unpack_from(">I", data, sect + off + 0x30)[0]
        recw = FLAG_RECW.get(flag, 3)
        idxbytes = 4 + F * recw
        if idxbytes < D - 0x20:
            out.append((sect_ram + C + idxbytes, D - idxbytes, f"mesh{k} C-trail"))
        log(f"PLAN: mesh{k} C=0x{C:X} D=0x{D:X} F={F} recw={recw} idx=0x{idxbytes:X}")
    return out


# ---------------- command channel (UNIX socket) ----------------

class CmdChan:
    def __init__(self, path):
        try:
            os.unlink(path)
        except OSError:
            pass
        self.conn = None
        self.lsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.lsock.bind(path)
        self.lsock.listen(1)
        self.lsock.setblocking(False)
        self.buf = b""

    def accept(self):
        if self.conn is None:
            try:
                self.conn, _ = self.lsock.accept()
                self.conn.setblocking(False)
                self.buf = b""
                log("CMD: client connected")
            except (BlockingIOError, socket.timeout):
                pass
        return self.conn

    def poll(self):
        """Return a list of command strings (possibly empty)."""
        c = self.accept()
        if c is None:
            return []
        cmds = []
        try:
            while True:
                chunk = c.recv(4096)
                if not chunk:
                    self.conn.close()
                    self.conn = None
                    log("CMD: client disconnected")
                    return cmds
                self.buf += chunk
                while b"\n" in self.buf:
                    line, self.buf = self.buf.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        cmds.append(line.decode("latin1"))
        except (BlockingIOError, socket.timeout):
            pass
        return cmds

    def reply(self, msg: str):
        try:
            if self.conn:
                self.conn.sendall((msg + "\n").encode())
        except Exception:
            pass


# ---------------- driver state machine ----------------

class Driver:
    def __init__(self):
        self.stub = Stub()
        self.cmd = CmdChan(SOCK)
        self.stop_count = 0
        self.watched = []          # (addr, len, label)
        self.dump_n = 0
        self.armed = False

    def state_line(self):
        pc = self.stub.read_reg(64)
        lr = self.stub.read_reg(67)
        return f"pc=0x{pc:08X} lr=0x{lr:08X}"

    def handle_dispatch(self):
        r3 = self.stub.read_reg(3)
        rec = self.stub.read_mem(r3, 0x30) if r3 else b""
        ctype = int.from_bytes(rec[8:12], "big") if len(rec) >= 12 else -1
        c14 = int.from_bytes(rec[20:24], "big") if len(rec) >= 24 else 0
        c18 = int.from_bytes(rec[24:28], "big") if len(rec) >= 28 else 0
        c20 = int.from_bytes(rec[32:36], "big") if len(rec) >= 36 else 0
        head = self.stub.read_mem(c18, 32) if c18 else b""
        tag = ""
        if head[:4] == b"TSFB":
            sz = int.from_bytes(head[4:8], "big")
            tag = f"TSFB sz=0x{sz:X}"
        log(f"[{self.stop_count}] DISPATCH type={ctype} c14=0x{c14:08X} "
            f"c18=0x{c18:08X} c20=0x{c20:08X} {tag}")
        if not tag.startswith("TSFB"):
            return
        # peek the chunk table: structural check for a level part
        peek = self.stub.read_mem(c18, 0x1000)
        if len(peek) < 0x30:
            return
        try:
            hdrx_size = struct.unpack_from(">I", peek, 0x10)[0]
            n = struct.unpack_from(">I", peek, 0x18)[0]
        except Exception:
            return
        if not (0x20 < hdrx_size < 0x10000) or not (2 <= n <= 0x400):
            log(f"[{self.stop_count}]   peek: hdrx=0x{hdrx_size:X} n={n} — skipping")
            return
        sizes = [struct.unpack_from(">I", peek, 0x20 + 16 * i)[0]
                 for i in range(min(n, (0x1000 - 0x28) // 16))]
        sect0 = sizes[0] if sizes else 0
        if n < 20 or sect0 < 0x8000:
            log(f"[{self.stop_count}]   peek: n={n} sect0=0x{sect0:X} — not a level part, skipping")
            return
        if self.armed:
            log(f"[{self.stop_count}]   level part, already armed — skipping dump")
            return
        tot = 8 + int.from_bytes(head[4:8], "big")
        tot = min(tot, 0x300000)
        log(f"[{self.stop_count}]   LEVEL PART: dumping staging buffer 0x{tot:X} bytes...")
        data = self.stub.read_mem(c18, tot)
        log(f"[{self.stop_count}]   dumped {len(data)} bytes")
        if len(data) < 0x1000:
            return
        fn = f"{DUMP_DIR}/trb_{self.dump_n:02d}.bin"
        open(fn, "wb").write(data)
        self.dump_n += 1
        log(f"[{self.stop_count}]   saved {fn}")
        t = parse_trb(data)
        if not t:
            return
        nms = [k for k in t["symbs"] if k.startswith("W0C0M")]
        log(f"[{self.stop_count}]   symbs={len(t['symbs'])} meshes={len(nms)} chunks={len(t['sizes'])}")
        if not nms:
            return
        self.watched = plan_watchpoints(data, c18)
        for a, l, lab in self.watched:
            ok = self.stub.watch(a, l, True)
            log(f"[{self.stop_count}]   WATCH {lab} 0x{a:08X} len=0x{l:X}: {'OK' if ok else 'FAIL'}")
        self.armed = True
        log(f"[{self.stop_count}]   WATCHPOINTS ARMED ({len(self.watched)})")

    def handle_stop(self):
        pc = self.stub.read_reg(64)
        self.stop_count += 1
        if pc == BP_DISPATCH:
            self.handle_dispatch()
            return
        lr = self.stub.read_reg(67)
        regs = {n: self.stub.read_reg(n) for n in
                (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)}
        code = self.stub.read_mem(pc & ~3, 0x40)
        log(f"[{self.stop_count}] *** READER STOP *** {self.state_line()}")
        log(f"[{self.stop_count}]   r2=0x{regs[2]:08X} r3=0x{regs[3]:08X} r4=0x{regs[4]:08X} "
            f"r5=0x{regs[5]:08X} r6=0x{regs[6]:08X} r7=0x{regs[7]:08X} r8=0x{regs[8]:08X}")
        log(f"[{self.stop_count}]   r9=0x{regs[9]:08X} r10=0x{regs[10]:08X} "
            f"r11=0x{regs[11]:08X} r12=0x{regs[12]:08X}")
        if code:
            log(f"[{self.stop_count}]   code: {code.hex(' ')}")
        # which watched range was likely hit? (address being read is often in a reg)
        for a, l, lab in self.watched:
            for rv in list(regs.values()) + [pc, lr]:
                if a <= rv < a + l:
                    log(f"[{self.stop_count}]   <- within {lab} (0x{a:08X}+0x{rv-a:X})")
                    break

    def run(self):
        ok = self.stub.bp(BP_DISPATCH)
        log(f"dispatcher BP @0x{BP_DISPATCH:08X}: {'OK' if ok else 'FAIL'}")
        if not ok:
            log("FATAL: cannot set BP — holding")
            while True:
                time.sleep(3600)

        hold = True
        running = False
        log("HOLDING after connect — game paused; awaiting 'go' to resume ("
            f"pc=0x{self.stub.read_reg(64):08X} lr=0x{self.stub.read_reg(67):08X} "
            f"r1=0x{self.stub.read_reg(1):08X} r3=0x{self.stub.read_reg(3):08X})")
        while True:
            # serve command channel
            for cmdline in self.cmd.poll():
                log(f"CMD: {cmdline}")
                parts = cmdline.split()
                if not parts:
                    continue
                c = parts[0]
                try:
                    if c == "mem":
                        d = self.stub.read_mem(int(parts[1], 0), int(parts[2], 0))
                        self.cmd.reply(f"mem[{parts[1]}:+{parts[2]}] = {d.hex(' ') if d else 'ERR'}")
                    elif c == "reg":
                        v = self.stub.read_reg(int(parts[1], 0))
                        self.cmd.reply(f"reg{parts[1]} = 0x{v:08X}" if v else "ERR")
                    elif c == "bp":
                        ok = self.stub.bp(int(parts[1], 0), True)
                        self.cmd.reply(f"bp {'OK' if ok else 'FAIL'}")
                    elif c == "nobp":
                        ok = self.stub.bp(int(parts[1], 0), False)
                        self.cmd.reply(f"nobp {'OK' if ok else 'FAIL'}")
                    elif c == "watch":
                        ok = self.stub.watch(int(parts[1], 0), int(parts[2], 0), True)
                        self.cmd.reply(f"watch {'OK' if ok else 'FAIL'}")
                    elif c == "nowatch":
                        ok = self.stub.watch(int(parts[1], 0), int(parts[2], 0), False)
                        self.cmd.reply(f"nowatch {'OK' if ok else 'FAIL'}")
                    elif c == "hold":
                        hold = True
                        self.cmd.reply("holding")
                    elif c == "go":
                        hold = False
                        self.cmd.reply("resuming")
                    elif c == "state":
                        self.cmd.reply("STOPPED " + self.state_line() if not running else "RUNNING")
                    elif c == "watched":
                        self.cmd.reply(f"{len(self.watched)} regions: " +
                                       ", ".join(f"{lab}@{a:X}+{l:X}" for a, l, lab in self.watched))
                    elif c == "quit":
                        log("QUIT ignored — never exit (kills the stub)")
                        self.cmd.reply("ignored")
                    else:
                        self.cmd.reply("?unknown")
                except Exception as e:
                    log(f"CMD ERR {e}")
                    self.cmd.reply(f"ERR {e}")

            # state machine
            if running:
                stop = self.stub.wait_stop()
                if stop is None:
                    log("NO STOP (timeout) — game idle; holding")
                    running = False
                    hold = True
                    continue
                running = False
                log(f"STOP packet: {stop}")
                self.handle_stop()
                if self.stop_count >= MAX_STOPS:
                    log(f"reached MAX_STOPS={MAX_STOPS} — holding")
                    hold = True
                continue
            if not hold:
                self.stub.continue_run()
                running = True


def main():
    os.makedirs(DUMP_DIR, exist_ok=True)
    d = Driver()
    d.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        print(tb, flush=True)
        with open(LOG, "a") as f:
            f.write("FATAL: " + tb + "\n")
        time.sleep(3600)
