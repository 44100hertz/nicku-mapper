#!/usr/bin/env python3
"""
Raw GDB remote protocol client for Dolphin's GDB stub.
Bypasses gdb entirely — speaks the stub protocol directly.
"""
import socket
import sys
import time
import struct

HOST = "127.0.0.1"
PORT = 2159


class GDBRaw:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        self.sock.settimeout(30)
        self.connected = True
        return self

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
        self.connected = False

    def checksum(self, cmd: bytes) -> bytes:
        return f"{sum(cmd) & 0xFF:02x}".encode()

    def send_raw(self, data: bytes) -> bytes:
        self.sock.sendall(data)
        return self.sock.recv(1)  # ack

    def cmd(self, c: str) -> bytes:
        """Send $cmd#chk, return reply bytes (without $ # chk)."""
        c = c.encode() if isinstance(c, str) else c
        pkt = b"$" + c + b"#" + self.checksum(c)
        ack = self.send_raw(pkt)
        if ack != b"+":
            return b""
        # read reply
        buf = b""
        while True:
            ch = self.sock.recv(1)
            if ch == b"$":
                buf = b""
                continue
            if ch == b"#":
                chk = self.sock.recv(2)
                return buf
            buf += ch

    # --- protocol helpers ---
    def q(self, q: str) -> bytes:
        return self.cmd(q)

    def read_reg(self, reg_id: int) -> int:
        """Read a single register via 'p'. Returns value or None."""
        r = self.cmd(f"p{reg_id:02x}")
        if not r:
            return None
        return int(r, 16)

    def read_regs(self) -> dict:
        """Read the 'g' reply (GPRs only per stub) and parse GPRs."""
        r = self.cmd("g")
        if not r:
            return {}
        out = {}
        for i in range(32):
            hexv = r[i * 8:(i + 1) * 8]
            if hexv:
                out[f"r{i}"] = int(hexv, 16)
        return out

    def read_mem(self, addr: int, length: int) -> bytes:
        r = self.cmd(f"m{addr:x},{length:x}")
        if not r or r in (b"E00", b"E01"):
            return None
        return bytes.fromhex(r.decode())

    def write_mem(self, addr: int, data: bytes) -> bool:
        r = self.cmd(f"M{addr:x},{len(data):x}:" + data.hex())
        return r == b"OK"

    def breakpoint(self, addr: int, add: bool = True) -> bool:
        r = self.cmd(f"Z{0 if add else 1}0,{addr:x},4")
        return r == b"OK"

    def continue_run(self):
        """Continue (non-blocking send; stub resumes game)."""
        self.cmd("c")

    def interrupt(self):
        """Send 0x03 to break the running game."""
        self.sock.sendall(b"\x03")

    def stop_reply(self) -> dict:
        """Parse a T stop reply into {signal, regs:{id:value}}."""
        r = self.cmd("?")
        if not r:
            return {}
        out = {"raw": r, "signal": None, "regs": {}}
        try:
            out["signal"] = int(r[1:3], 16)
            # parse reg:value; pairs after byte 3
            i = 3
            while i + 2 <= len(r):
                rid = int(r[i:i + 2], 16)
                i += 2
                if i < len(r) and r[i:i + 1] == b":":
                    i += 1
                    end = r.find(b";", i)
                    if end == -1:
                        break
                    val = int(r[i:end], 16)
                    out["regs"][rid] = val
                    i = end + 1
                else:
                    break
        except Exception:
            pass
        return out


def main():
    args = sys.argv[1:]
    if args and args[0] == "repl":
        # Persistent mode: hold one connection, read commands from stdin
        g = GDBRaw()
        try:
            g.connect()
            print("CONNECTED")
        except Exception as e:
            print(f"CONNECT FAIL: {e}")
            sys.exit(1)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            c = parts[0]
            try:
                if c == "query":
                    s = g.stop_reply()
                    print("STOP raw:", s.get("raw"))
                    regs = s.get("regs", {})
                    print(f"  pc={regs.get(64, 0):08X} r1={regs.get(1, 0):08X}")
                    gprs = g.read_regs()
                    print("  gprs:", " ".join(f"r{i}={gprs.get(f'r{i}', 0):08X}" for i in range(0, 8)))
                elif c == "mem":
                    addr = int(parts[1], 0)
                    length = int(parts[2], 0)
                    d = g.read_mem(addr, length)
                    print(f"MEM {addr:08X} {length:02X}: {d.hex(' ') if d else 'ERR'}")
                elif c == "reg":
                    rid = int(parts[1], 0)
                    v = g.read_reg(rid)
                    print(f"REG {rid}: {v:08X}" if v is not None else f"REG {rid}: ERR")
                elif c == "bp":
                    print("BP", "OK" if g.breakpoint(int(parts[1], 0)) else "FAIL")
                elif c == "nobp":
                    print("NOBP", "OK" if g.breakpoint(int(parts[1], 0), add=False) else "FAIL")
                elif c == "cont":
                    # send 'c' but DON'T block waiting for reply — stub replies only on stop
                    pkt = b"$c#63"
                    g.sock.sendall(pkt)
                    ack = g.sock.recv(1)
                    print(f"RUNNING (ack={ack})")
                    # poll socket for stop reply AND stdin for commands
                    import select as _sel
                    g.sock.settimeout(None)
                    while True:
                        r, _, _ = _sel.select([sys.stdin, g.sock], [], [], 0.5)
                        for fd in r:
                            if fd is sys.stdin:
                                line = sys.stdin.readline()
                                if not line:
                                    continue
                                parts = line.strip().split()
                                if parts and parts[0] == "intr":
                                    g.sock.sendall(b"\x03")
                                    print("INTR sent")
                                elif parts and parts[0] == "wait":
                                    print("waiting...")
                                elif parts and parts[0] == "exit":
                                    g.close()
                                    sys.exit(0)
                                else:
                                    print(f"?busy cmd ignored: {line.strip()}")
                            elif fd is g.sock:
                                # stop reply arrived
                                buf = b""
                                while True:
                                    ch = g.sock.recv(1)
                                    if ch == b"$":
                                        buf = b""
                                    elif ch == b"#":
                                        g.sock.recv(2)
                                        break
                                    else:
                                        buf += ch
                                print(f"STOP: {buf}")
                                g.sock.settimeout(60)
                                break
                elif c == "intr":
                    g.interrupt()
                    time.sleep(0.5)
                    g.sock.settimeout(3)
                    try:
                        buf = b""
                        while True:
                            ch = g.sock.recv(1)
                            if ch == b"$":
                                buf = b""
                            elif ch == b"#":
                                g.sock.recv(2)
                                break
                            else:
                                buf += ch
                        print(f"INTR STOP: {buf}")
                    except socket.timeout:
                        print("INTR: no stop reply")
                    g.sock.settimeout(30)
                elif c == "wait":
                    # wait for an async stop reply
                    g.sock.settimeout(10)
                    try:
                        buf = b""
                        while True:
                            ch = g.sock.recv(1)
                            if ch == b"$":
                                buf = b""
                            elif ch == b"#":
                                g.sock.recv(2)
                                break
                            else:
                                buf += ch
                        print(f"WAIT STOP: {buf}")
                    except socket.timeout:
                        print("WAIT: nothing")
                    g.sock.settimeout(30)
                elif c == "cmd":
                    print("CMD", g.cmd(parts[1]))
                elif c == "exit":
                    break
                else:
                    print("??")
            except Exception as e:
                print(f"ERR: {e}")
                # keep the connection alive; continue the loop
        g.close()
        sys.exit(0)

    if len(args) < 1:
        print("usage: gdbraw.py repl | <cmd> [args]")
        print("  repl                 - persistent session, commands from stdin")
        print("  query                - connect, get stop reply, show pc+r1, gprs")
        print("  mem <addr> <len>     - read memory as hex")
        print("  reg <id>             - read single register")
        print("  bp <addr>            - set breakpoint")
        print("  nobp <addr>          - remove breakpoint")
        print("  cont                 - continue (game runs)")
        print("  intr                 - send interrupt (0x03)")
        print("  cmd <raw>            - send raw command")
        sys.exit(1)

    g = GDBRaw()
    g.connect()
    cmd = args[0]

    if cmd == "query":
        s = g.stop_reply()
        print("stop reply:", s.get("raw"))
        print("signal:", s.get("signal"))
        regs = s.get("regs", {})
        print("pc (64):", f"0x{regs.get(64, 0):08X}" if 64 in regs else "n/a")
        print("r1  (1):", f"0x{regs.get(1, 0):08X}" if 1 in regs else "n/a")
        gprs = g.read_regs()
        print("r3:", f"0x{gprs.get('r3', 0):08X}", "r4:", f"0x{gprs.get('r4', 0):08X}")
    elif cmd == "mem":
        addr = int(args[1], 0)
        length = int(args[2], 0)
        d = g.read_mem(addr, length)
        print(f"mem[{addr:08X}:+{length}] =", d.hex(" ") if d else "ERR")
    elif cmd == "reg":
        rid = int(args[1], 0)
        print(f"reg {rid}:", hex(g.read_reg(rid)) if g.read_reg(rid) is not None else "ERR")
    elif cmd == "bp":
        print("bp:", "OK" if g.breakpoint(int(args[1], 0)) else "FAIL")
    elif cmd == "nobp":
        print("nobp:", "OK" if g.breakpoint(int(args[1], 0), add=False) else "FAIL")
    elif cmd == "cont":
        g.continue_run()
        print("continue sent")
    elif cmd == "intr":
        g.interrupt()
        print("interrupt sent")
    elif cmd == "cmd":
        r = g.cmd(args[1])
        print("reply:", r)
    else:
        print("unknown cmd")
    g.close()


if __name__ == "__main__":
    main()
