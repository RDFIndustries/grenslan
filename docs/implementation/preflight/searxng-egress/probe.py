"""Disposable observer for SearXNG's outbound behaviour on a network with no route out.

Runs inside a container on the same Docker --internal network as SearXNG:
- UDP 53: answers every A query with this container's address and logs the
  name; AAAA and other types get an empty answer.
- TCP 443: logs the TLS ClientHello's SNI, then closes.
- TCP 80: logs the HTTP request line and Host header, then closes.
- TCP 3128: an HTTP proxy that logs CONNECT targets (or absolute-form request
  URLs), then closes.
Nothing is forwarded anywhere. Each event is one JSON line on stdout.
"""

import json
import socket
import socketserver
import struct
import sys
import threading
import time

ADDRESS = sys.argv[1]


def log(kind, **fields):
    print(json.dumps({"t": round(time.time(), 3), "kind": kind, **fields}), flush=True)


def dns_name(packet, offset):
    labels = []
    while True:
        length = packet[offset]
        if length == 0:
            return ".".join(labels), offset + 1
        labels.append(packet[offset + 1 : offset + 1 + length].decode("ascii", "replace"))
        offset += 1 + length


class Dns(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        name, offset = dns_name(data, 12)
        qtype = struct.unpack("!H", data[offset : offset + 2])[0]
        log("dns", name=name, qtype={1: "A", 28: "AAAA"}.get(qtype, qtype), client=self.client_address[0])
        question = data[12 : offset + 4]
        flags = 0x8180
        answers = b""
        count = 0
        if qtype == 1:
            answers = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 5, 4) + socket.inet_aton(ADDRESS)
            count = 1
        header = data[:2] + struct.pack("!HHHHH", flags, 1, count, 0, 0)
        sock.sendto(header + question + answers, self.client_address)


def sni(hello):
    try:
        if hello[0] != 0x16:
            return None
        body = hello[5:]
        offset = 4 + 2 + 32
        offset += 1 + body[offset]
        offset += 2 + struct.unpack("!H", body[offset : offset + 2])[0]
        offset += 1 + body[offset]
        end = offset + 2 + struct.unpack("!H", body[offset : offset + 2])[0]
        offset += 2
        while offset < end:
            kind, length = struct.unpack("!HH", body[offset : offset + 4])
            if kind == 0:
                name_length = struct.unpack("!H", body[offset + 7 : offset + 9])[0]
                return body[offset + 9 : offset + 9 + name_length].decode("ascii", "replace")
            offset += 4 + length
    except (IndexError, struct.error):
        return "unparsed"
    return None


class Sink(socketserver.BaseRequestHandler):
    def handle(self):
        port = self.server.server_address[1]
        self.request.settimeout(3)
        try:
            data = self.request.recv(16384)
        except OSError:
            data = b""
        if port == 443:
            log("tls", sni=sni(data), client=self.client_address[0])
        elif port == 80:
            lines = data.split(b"\r\n")
            host = next((line[5:].strip().decode("latin-1") for line in lines if line.lower().startswith(b"host:")), None)
            log("http", request=lines[0].decode("latin-1")[:200], host=host, client=self.client_address[0])
        else:
            log("proxy", request=data.split(b"\r\n")[0].decode("latin-1")[:300], client=self.client_address[0])
            self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")


class Threaded(socketserver.ThreadingMixIn):
    daemon_threads = True
    allow_reuse_address = True


class Udp(Threaded, socketserver.UDPServer):
    pass


class Tcp(Threaded, socketserver.TCPServer):
    pass


servers = [Udp(("0.0.0.0", 53), Dns)] + [Tcp(("0.0.0.0", port), Sink) for port in (80, 443, 3128)]
for server in servers:
    threading.Thread(target=server.serve_forever, daemon=True).start()
log("ready", address=ADDRESS)
threading.Event().wait()
