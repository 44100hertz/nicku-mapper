#!/usr/bin/env python3
"""JSON-RPC line client for the grilled-dolphin control server."""
import json, socket, sys, time

HOST, PORT = "127.0.0.1", 2200

def call(method, params=None, host=HOST, port=PORT):
    req = {"id": 1, "method": method, "params": params or []}
    s = socket.create_connection((host, port), timeout=30)
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

def wait_state(target, timeout=300, host=HOST, port=PORT):
    """Block until bridge.status state == target (or timeout)."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            st = call("bridge.status", host=host, port=port)
            if st.get("state") == target:
                return st
        except Exception:
            pass
        time.sleep(0.5)
    return call("bridge.status", host=host, port=port)

if __name__ == "__main__":
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "wait":
        print(json.dumps(wait_state(args[0], int(args[1]) if len(args) > 1 else 300)))
    else:
        params = [a if not a.lstrip("-").isdigit() else int(a) for a in args]
        # allow JSON for dict params
        def conv(a):
            if a.startswith("{") or a.startswith("["):
                return json.loads(a)
            try:
                return int(a, 0)  # handles 0x hex and decimal
            except ValueError:
                return a
        params = [conv(a) for a in args]
        print(json.dumps(call(cmd, params)))
