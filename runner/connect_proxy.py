#!/usr/bin/env python3
"""SSH ProxyCommand: CONNECT through the egress HTTP proxy from HTTPS_PROXY env.
Usage: connect_proxy.py <dest_host> <dest_port>
Bridges stdin/stdout to the tunneled socket. Credentials come only from env,
never from argv, so nothing secret lands in process listings beyond the
pre-existing environment.
"""
import os
import sys
import socket
import base64
import select
import fcntl
import urllib.parse


def main():
    host, port = sys.argv[1], int(sys.argv[2])
    proxy = urllib.parse.urlparse(os.environ.get("HTTPS_PROXY", "") or os.environ.get("https_proxy", ""))
    if not proxy.hostname:
        sys.stderr.write("no HTTPS_PROXY set\n")
        return 1
    try:
        s = socket.create_connection((proxy.hostname, proxy.port or 3128), timeout=20)
    except OSError as e:
        sys.stderr.write(f"proxy tcp failed: {e}\n")
        return 1
    auth = base64.b64encode(f"{proxy.username or ''}:{proxy.password or ''}".encode()).decode()
    req = (f"CONNECT {host}:{port} HTTP/1.1\r\n"
           f"Host: {host}:{port}\r\n"
           f"Proxy-Authorization: Basic {auth}\r\n"
           f"Proxy-Connection: Keep-Alive\r\n\r\n")
    try:
        s.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            d = s.recv(4096)
            if not d:
                sys.stderr.write("proxy closed during CONNECT\n")
                return 1
            resp += d
    except OSError as e:
        sys.stderr.write(f"proxy io failed: {e}\n")
        return 1
    status = resp.split(b"\r\n", 1)[0].decode(errors="replace")
    if " 200" not in status:
        sys.stderr.write(f"CONNECT rejected: {status}\n")
        return 1
    for fd in (0, 1):
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    s.setblocking(False)
    sf = s.fileno()
    while True:
        try:
            r, _, _ = select.select([0, sf], [], [], 300)
        except (OSError, ValueError):
            break
        if 0 in r:
            try:
                d = os.read(0, 65536)
            except BlockingIOError:
                d = b""
            if not d:
                break
            try:
                s.sendall(d)
            except OSError:
                break
        if sf in r:
            try:
                d = s.recv(65536)
            except BlockingIOError:
                d = b""
            if not d:
                break
            try:
                os.write(1, d)
            except OSError:
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
