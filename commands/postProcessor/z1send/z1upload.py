"""Send a file to a stock Makera Z1's SD card over Wi-Fi, or fetch one back. Standard library only, one
file, so it can be copied into a Fusion 360 add-in as is.

    python z1upload.py upload <ip|discover> local.cnc [/sd/gcodes/name.cnc] [--verify] [--force]
    python z1upload.py download <ip|discover> /sd/gcodes/name.cnc out.cnc
    python z1upload.py discover

    from z1upload import upload
    r = upload("192.168.1.100", r"E:\\...\\Setup1.cnc")          # -> /sd/gcodes/Setup1.cnc
    print(r.ok, r.message)

Protocol: reference/upload_protocol_notes.md (upload) and reference/download_protocol_notes.md.
The ESP32 board answers these frames itself; nothing reaches the motion board. Frame:
86 68 | len u16 BE | type | payload | CRC-16/XMODEM u16 BE | 55 AA.

Upload, client C, machine M (the machine asks for every step):
    C: B0 "upload <path>\\n"         (spaces in the path sent as 0x01)
    C: B1 <md5, 32 lowercase hex>     M writes it as the file's MD5 cache, then asks for the file view
    M: B2 (empty)                     C: B2 u32 packet count + u16 packet size
    M: B3 u32 seq                     C: B3 u32 seq + data (<= 8192 bytes)      ... repeated
    M: B4 "ok\\r\\n" then 0x90 "Info: upload success: <path>."
    M: B5 <text> = failed / gave up,  B6 <text> = resend your last frame,  0x91 = another client is transferring.
The file is stored exactly as sent (uncompressed); Makera's own app sends files uncompressed too.

Safety: refuses to upload while the machine is running or holding a job, and never overwrites the file
that is playing. A failed or refused upload never raises from upload(); check result.ok.
"""
from __future__ import annotations

import hashlib
import os
import socket
import struct
import sys
import time
from dataclasses import dataclass

TCP_PORT = 2222
DISCOVERY_PORT = 3333
GCODES = "/sd/gcodes/"

B_START, B_MD5, B_VIEW, B_DATA, B_DONE, B_CANCEL, B_RETRY, B_PLAYING = range(0xB0, 0xB8)
T_RT, T_STATUS, T_INFO, T_BUSY = 0xA1, 0x81, 0x90, 0x91

PACKET_SIZE = 4096            # what Makera's app uses [I]; the ESP32 takes up to 8192
MAX_PACKET = 8192
REPLY_TIMEOUT = 3.0           # per request; the ESP32 gives up after 9 s of silence
MAX_TRIES = 5


# --- framing ---------------------------------------------------------------------------------
def _crc_table():
    t = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) if c & 0x8000 else (c << 1)
        t.append(c & 0xFFFF)
    return t


_TABLE = _crc_table()


def crc16(data: bytes) -> int:
    c = 0
    for b in data:
        c = ((c << 8) & 0xFFFF) ^ _TABLE[((c >> 8) ^ b) & 0xFF]
    return c


def frame(ptype: int, payload: bytes = b"") -> bytes:
    body = struct.pack(">HB", len(payload) + 3, ptype) + payload
    return b"\x86\x68" + body + struct.pack(">H", crc16(body)) + b"\x55\xaa"


class _Decoder:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(b"\x86\x68")
            if i < 0:
                del self.buf[:-1]
                return out
            del self.buf[:i]
            if len(self.buf) < 4:
                return out
            ln = struct.unpack(">H", self.buf[2:4])[0]
            if ln < 3 or ln > MAX_PACKET + 7:
                del self.buf[:2]
                continue
            total = ln + 6
            if len(self.buf) < total:
                return out
            body = bytes(self.buf[2:2 + ln])
            crc, foot = struct.unpack(">HH", self.buf[2 + ln:total])
            if foot != 0x55AA or crc != crc16(body):
                del self.buf[:2]
                continue
            out.append((body[2], body[3:]))
            del self.buf[:total]


class TransferError(Exception):
    pass


class _Link:
    """One TCP connection. recv() returns the next frame of the wanted types; everything else
    (firmware version, status text the machine sends on its own) is skipped."""

    def __init__(self, host: str, port: int, connect_timeout: float):
        self.sock = socket.create_connection((host, port), timeout=connect_timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.dec = _Decoder()
        self.pending = []
        self.last_sent = b""

    def send(self, data: bytes):
        self.last_sent = data
        self.sock.sendall(data)

    def recv(self, types, timeout: float):
        end = time.monotonic() + timeout
        while True:
            for k, (t, p) in enumerate(self.pending):
                if t in types:
                    del self.pending[k]
                    return t, p
            self.pending = [x for x in self.pending if x[0] in (T_BUSY, B_CANCEL)][-4:]
            left = end - time.monotonic()
            if left <= 0:
                return None
            self.sock.settimeout(left)
            try:
                data = self.sock.recv(65536)
            except socket.timeout:
                return None
            if not data:
                raise TransferError("the machine closed the connection")
            self.pending += self.dec.feed(data)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def _text(p: bytes) -> str:
    return p.decode("utf-8", "replace").strip().strip("\x00")


def _wire_path(remote: str) -> bytes:
    if not remote.startswith("/sd/"):
        raise TransferError(f"remote path must start with /sd/: {remote!r}")
    bad = [c for c in remote if c in "?*!~\\" or ord(c) < 0x20 or ord(c) > 0x7E]
    if bad:
        raise TransferError(f"remote path has characters the machine can't take: {''.join(sorted(set(bad)))!r}")
    if ".." in remote.split("/"):
        raise TransferError("remote path can't contain '..'")
    data = remote.replace(" ", "\x01").encode("ascii")
    if len(data) > 500:
        raise TransferError("remote path is too long")
    return data


def remote_name(local_path: str, folder: str = GCODES) -> str:
    """/sd/gcodes/<file name>, keeping the name as it is."""
    return folder.rstrip("/") + "/" + os.path.basename(local_path)


# --- machine state ---------------------------------------------------------------------------
def _machine_state(link: _Link) -> str:
    link.send(frame(T_RT, b"?"))
    r = link.recv({T_STATUS}, REPLY_TIMEOUT)
    if not r:
        raise TransferError("the machine didn't answer a status request")
    s = _text(r[1])
    return s[1:].split("|")[0].split(":")[0] if s.startswith("<") else s


def _playing_file(link: _Link) -> str:
    link.send(frame(B_PLAYING))
    r = link.recv({B_PLAYING}, REPLY_TIMEOUT)
    return _text(r[1]).split("|")[0] if r else ""


# --- upload ----------------------------------------------------------------------------------
@dataclass
class Result:
    ok: bool
    message: str
    remote_path: str = ""
    size: int = 0
    seconds: float = 0.0
    verified: bool = False


class _Busy(TransferError):
    """Retryable: another client holds the transfer slot, or a leftover transfer got in the way."""


def _flush(link: _Link):
    """End any transfer still running for our connection slot before starting one.

    The ESP32 keeps one owner slot (FUN_42012fa0). A transfer whose client dropped keeps running until
    9 s pass without a frame, and the next connection given that slot inherits it: its requests come to
    us and our frames go to it (seen on the Z1, 2026-11-16). Every 0xB0 from the owner queues another
    handler, and each handler clears the owner when it ends, so a queued one runs ownerless and never
    hears us. So: never send 0xB0 while something may be running. One 0xB5 first ends a leftover
    transfer (an upload ends silently, a download replies); with nothing running, or another client
    owning the slot, the board drops it."""
    link.send(frame(B_CANCEL))
    link.recv(set(), 0.3)                          # drain whatever the leftover sent
    link.pending.clear()


def _upload(link: _Link, data: bytes, remote: str, packet_size: int, progress) -> None:
    wire = _wire_path(remote)
    md5 = hashlib.md5(data).hexdigest().encode("ascii")
    count = max(1, -(-len(data) // packet_size))
    _flush(link)
    link.send(frame(B_START, b"upload " + wire + b"\n"))
    link.send(frame(B_MD5, md5))
    view_sent = False
    tries = 0
    want = {B_MD5, B_VIEW, B_DATA, B_DONE, B_CANCEL, B_RETRY, T_BUSY}
    while True:
        r = link.recv(want, REPLY_TIMEOUT)
        if r is None:
            tries += 1
            if tries >= MAX_TRIES:
                raise TransferError("the machine stopped answering")
            link.send(link.last_sent)              # stop-and-wait: send our last frame again (never a B0)
            continue
        t, p = r
        if t == T_BUSY:
            raise _Busy("another app is sending or fetching a file right now: " + _text(p))
        if t == B_CANCEL:
            msg = _text(p)
            if not view_sent and any(k in msg.lower() for k in ("time out", "canceled", "too many")):
                raise _Busy("a leftover transfer ended in the way: " + msg)
            raise TransferError(msg or "the machine cancelled the upload")
        if t == B_RETRY:                           # e.g. "Error: File Write error!retry..."
            tries += 1
            if tries >= MAX_TRIES:
                raise TransferError(_text(p) or "too many retries")
            link.send(link.last_sent)
            continue
        tries = 0
        if t == B_MD5:                             # the machine didn't get our MD5: it asks again
            link.send(frame(B_MD5, md5))
        elif t == B_VIEW:
            link.send(frame(B_VIEW, struct.pack(">IH", count, packet_size)))
            view_sent = True
        elif t == B_DATA:
            seq = struct.unpack(">I", p[:4])[0]
            if not view_sent:                      # a packet request before our file view: not ours
                link.send(frame(B_CANCEL))
                raise _Busy(f"a leftover upload asked for packet {seq}")
            if not 1 <= seq <= count:
                raise TransferError(f"the machine asked for packet {seq} of {count}")
            chunk = data[(seq - 1) * packet_size: seq * packet_size]
            link.send(frame(B_DATA, p[:4] + chunk))
            if progress:
                progress(min(len(data), seq * packet_size), len(data))
        elif t == B_DONE:
            end = time.monotonic() + 2.0           # then 0x90 "Info: upload success: <path>."
            while (r := link.recv({T_INFO}, max(0.0, end - time.monotonic()))) is not None:
                msg = _text(r[1])
                if "upload" in msg.lower():
                    if "error" in msg.lower() or ("success" in msg.lower() and remote not in msg):
                        raise TransferError(msg)
                    break
            return


def upload(host: str, local_path: str, remote_path: str | None = None, *, port: int = TCP_PORT,
           packet_size: int = PACKET_SIZE, verify: bool = False, allow_during_job: bool = False,
           progress=None, connect_timeout: float = 5.0, busy_wait: float = 15.0) -> Result:
    """Copy local_path to the machine's SD card (default /sd/gcodes/<file name>), replacing a file of
    the same name. If another client is transferring a file, keep trying for busy_wait seconds.
    Never raises for machine or network trouble: returns Result(ok=False, message)."""
    t0 = time.monotonic()
    remote = remote_path or remote_name(local_path)
    if not 1 <= packet_size <= MAX_PACKET:
        return Result(False, f"packet size must be 1..{MAX_PACKET}", remote)
    try:
        with open(local_path, "rb") as f:
            data = f.read()
    except OSError as e:
        return Result(False, f"can't read {local_path}: {e}", remote)
    try:
        link = _Link(host, port, connect_timeout)
    except OSError as e:
        return Result(False, f"can't reach the machine at {host}:{port}: {e}", remote, len(data))
    try:
        # Set the Wi-Fi board's clock first, as Makera's app does on every Wi-Fi connect (`syncTime`:
        # "time <Unix seconds>"), so the file gets today's date instead of 1980. ESP-local, answered "time = …".
        link.send(frame(0xA2, f"time {int(time.time())}".encode("ascii")))
        playing = _playing_file(link)
        if playing == remote:
            raise TransferError(f"{remote} is the file the machine is playing")
        if not allow_during_job:
            state = _machine_state(link)
            if playing or state in ("Run", "Hold", "Door", "Tool", "Home"):
                raise TransferError(f"the machine is busy ({'playing ' + playing if playing else state}); "
                                    "upload when it's idle")
        deadline = time.monotonic() + busy_wait
        while True:
            try:
                _upload(link, data, remote, packet_size, progress)
                break
            except _Busy:                          # Studio, or a dropped connection's leftover transfer
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1.0)
        verified = False
        if verify:
            back = _download(link, remote, None)
            if back != data:
                raise TransferError("uploaded, but the copy read back from the machine is different")
            verified = True
        return Result(True, f"sent {len(data)} bytes to {remote}" + (" and read it back" if verified else ""),
                      remote, len(data), time.monotonic() - t0, verified)
    except (TransferError, OSError) as e:
        try:
            link.send(frame(B_CANCEL))                 # free the machine's transfer slot
        except OSError:
            pass
        return Result(False, str(e), remote, len(data), time.monotonic() - t0)
    finally:
        link.close()


# --- download --------------------------------------------------------------------------------
def _request(link: _Link, req: bytes, types, what: str, resend: bool = True):
    link.send(req)
    for _ in range(MAX_TRIES if resend else 1):
        r = link.recv(types | {B_CANCEL, B_RETRY, T_BUSY}, REPLY_TIMEOUT if resend else 8.0)
        if r is None or r[0] == B_RETRY:
            if resend:
                link.send(req)
            continue
        if r[0] == T_BUSY:
            raise TransferError("another app is sending or fetching a file right now")
        if r[0] == B_CANCEL:
            raise TransferError(_text(r[1]) or f"the machine cancelled ({what})")
        return r
    raise TransferError(f"no answer from the machine ({what})")


def _download(link: _Link, remote: str, progress) -> bytes:
    """Fetch a file. Returns its bytes as stored (a QuickLZ copy in /sd/gcodes/.lz/ would be served
    instead of the file if one exists; see download_protocol_notes.md 2.5)."""
    # Never resend a 0xB0: each one queues a handler (see _flush).
    _flush(link)
    _, md5 = _request(link, frame(B_START, b"download " + _wire_path(remote) + b"\n"), {B_MD5}, "start",
                      resend=False)
    _, view = _request(link, frame(B_VIEW), {B_VIEW}, "file view")
    count, size = struct.unpack(">IH", view[:6])
    out = bytearray()
    for seq in range(1, count + 1):
        req = frame(B_DATA, struct.pack(">I", seq))
        for _ in range(MAX_TRIES):
            _, p = _request(link, req, {B_DATA}, f"packet {seq}")
            if struct.unpack(">I", p[:4])[0] == seq:
                break
        else:
            raise TransferError(f"packet {seq} never came")
        out += p[4:]
        if progress:
            progress(len(out), count * size)
    _request(link, frame(B_DONE), {B_DONE}, "done")
    link.recv({T_INFO}, 1.0)
    return bytes(out)


def download(host: str, remote_path: str, *, port: int = TCP_PORT, connect_timeout: float = 5.0,
             progress=None) -> bytes:
    """Fetch a file from the SD card. Raises TransferError / OSError on failure."""
    link = _Link(host, port, connect_timeout)
    try:
        return _download(link, remote_path, progress)
    except (TransferError, OSError):
        try:
            link.send(frame(B_CANCEL))
        except OSError:
            pass
        raise
    finally:
        link.close()


# --- discovery -------------------------------------------------------------------------------
def discover(timeout: float = 3.0) -> list[dict]:
    """Machines broadcasting on UDP 3333: [{'name', 'ip', 'port', 'busy'}]."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", DISCOVERY_PORT))
    found = {}
    end = time.monotonic() + timeout
    try:
        while (left := end - time.monotonic()) > 0:
            s.settimeout(left)
            try:
                data, _ = s.recvfrom(1024)
            except socket.timeout:
                break
            parts = [x.strip() for x in data.decode("ascii", "replace").strip().strip("<>\x00").split(",")]
            if len(parts) >= 3 and parts[2].isdigit():
                found[parts[1]] = {"name": parts[0], "ip": parts[1], "port": int(parts[2]),
                                   "busy": len(parts) > 3 and parts[3] == "1"}
    finally:
        s.close()
    return list(found.values())


def _local_subnets(limit: int = 4) -> list[str]:
    """This computer's private IPv4 /24 networks as 'a.b.c', the one with the default route first."""
    ips = []
    try:  # no packet is sent: connect() on UDP only picks the outgoing interface
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        ips += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    nets = []
    for ip in ips:
        a = ip.split(".")
        if len(a) != 4:
            continue
        private = a[0] == "10" or (a[0] == "172" and 16 <= int(a[1]) <= 31) or a[:2] == ["192", "168"]
        net = ".".join(a[:3])
        if private and net not in nets:
            nets.append(net)
    return nets[:limit]


def _is_machine(ip: str, port: int, connect_timeout: float):
    try:
        link = _Link(ip, port, connect_timeout)
    except OSError:
        return None
    try:
        link.send(frame(T_RT, b"?"))
        r = link.recv({T_STATUS}, 1.0)
        if not r:
            return None
        s = _text(r[1])
        state = s[1:].split("|")[0].split(":")[0] if s.startswith("<") else s
        return {"name": "Z1", "ip": ip, "port": port, "busy": state not in ("Idle", "")}
    except (OSError, TransferError):
        return None
    finally:
        link.close()


def probe(*, port: int = TCP_PORT, connect_timeout: float = 0.4, workers: int = 64) -> list[dict]:
    """Find machines without hearing their broadcasts, for when a firewall blocks inbound UDP (Fusion's
    own firewall rule can do that): try TCP <port> on every address of this computer's /24 networks and
    keep those that answer a status request with a Makera frame. About 2 s per network."""
    from concurrent.futures import ThreadPoolExecutor
    hosts = [f"{net}.{i}" for net in _local_subnets() for i in range(1, 255)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        found = pool.map(lambda h: _is_machine(h, port, connect_timeout), hosts)
        return [m for m in found if m]


# --- CLI -------------------------------------------------------------------------------------
def _host(arg: str) -> tuple[str, int]:
    if arg != "discover":
        h, _, p = arg.partition(":")
        return h, int(p) if p else TCP_PORT
    ms = discover()
    if len(ms) != 1:
        raise SystemExit(f"found {len(ms)} machines: {ms}; give the IP instead")
    return ms[0]["ip"], ms[0]["port"]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Send files to / fetch files from a stock Makera Z1.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("upload")
    u.add_argument("host")
    u.add_argument("local")
    u.add_argument("remote", nargs="?")
    u.add_argument("--verify", action="store_true", help="read the file back and compare")
    u.add_argument("--packet", type=int, default=PACKET_SIZE)
    d = sub.add_parser("download")
    d.add_argument("host")
    d.add_argument("remote")
    d.add_argument("local")
    sub.add_parser("discover")
    a = ap.parse_args(argv)

    def bar(done, total):
        print(f"\r{done}/{total} bytes", end="", flush=True)

    if a.cmd == "discover":
        for m in discover():
            print(m)
        return 0
    host, port = _host(a.host)
    if a.cmd == "upload":
        r = upload(host, a.local, a.remote, port=port, packet_size=a.packet, verify=a.verify, progress=bar)
        print()
        print(("OK: " if r.ok else "FAILED: ") + r.message + f" ({r.seconds:.1f} s)")
        return 0 if r.ok else 1
    data = download(host, a.remote, port=port, progress=bar)
    print()
    with open(a.local, "wb") as f:
        f.write(data)
    print(f"OK: {len(data)} bytes -> {a.local}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
