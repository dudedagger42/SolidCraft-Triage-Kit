"""Tiny SolidCraft control-channel client.

Usage as a module:  from sc import Sc; s = Sc(47600); s("ui.inspect")
Usage as a CLI:     python sc.py 47600 method '{"json": "params"}' [method params ...]
"""
import json
import os
import socket
import sys
import time


class Sc:
    def __init__(self, port=47600, timeout=90):
        tok_path = os.path.join(os.environ["LOCALAPPDATA"], "SolidCraft", "control", f"{port}.token")
        for _ in range(60):
            if os.path.exists(tok_path):
                break
            time.sleep(0.5)
        self.token = open(tok_path).read().strip()
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.buf = b""
        self.n = 0

    def __call__(self, method, params=None, check=True):
        self.n += 1
        req = {"id": self.n, "method": method, "params": params or {}}
        if self.n == 1:
            req["token"] = self.token
        self.sock.sendall((json.dumps(req) + "\n").encode())
        while b"\n" not in self.buf:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise RuntimeError("connection closed")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        rep = json.loads(line)
        if check and not rep.get("ok"):
            raise RuntimeError(f"{method} failed: {rep.get('error')}")
        return rep.get("result") if rep.get("ok") else rep

    def ex(self, command, params=None, check=True):
        return self(
            "engine.execute", {"command": command, "params": params or {}}, check=check
        )

    def at(self, **target):
        r = self("ui.at", target)
        if isinstance(r, list):
            return r[0], r[1]
        return r["x"], r["y"]


if __name__ == "__main__":
    port = int(sys.argv[1])
    s = Sc(port)
    args = sys.argv[2:]
    for i in range(0, len(args), 2):
        params = json.loads(args[i + 1]) if i + 1 < len(args) else {}
        print(json.dumps(s(args[i], params, check=False), indent=1)[:6000])
