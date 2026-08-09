#!/usr/bin/env python3
"""scan3cmd.py — send a command to the persistent scan3 driver (UNIX socket).
Usage: scan3cmd.py "mem 0x800217bc 0x40"   (or bare args)
"""
import socket
import sys

SOCK = "/tmp/scan3.sock"


def main():
    cmd = " ".join(sys.argv[1:]).strip()
    if not cmd:
        print("usage: scan3cmd.py '<command>'")
        return
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect(SOCK)
    except Exception as e:
        print(f"connect failed: {e} (driver not running?)")
        return
    s.sendall((cmd + "\n").encode())
    s.settimeout(20)
    try:
        data = s.recv(65536)
        print(data.decode().strip())
    except socket.timeout:
        print("(no reply — driver busy waiting for a stop; command may be processed later)")


if __name__ == "__main__":
    main()
