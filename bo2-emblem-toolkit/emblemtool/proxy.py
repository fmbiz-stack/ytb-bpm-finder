"""The MITM proxy your console points its network proxy setting at.

HTTPS (CONNECT) traffic is tunneled raw and never decrypted, so PSN sign-in
and normal console functionality keep working untouched. Plain HTTP requests
to the Demonware emblem-storage endpoint are the only thing inspected: in
CAPTURE mode the real response is saved, in Show mode it's replaced with
whichever emblem is currently selected (see broadcast.py).

Which requests count as emblem requests is decided in consoles.py, by the
shape of the request path rather than a hardcoded hostname - see that module
for why. The upshot here is that this file works with a PS3, PS4 or PS5
without being told which one it's talking to.
"""
import os
import socket
import threading
import time

from . import config
from . import consoles
from . import settings
from .state import read_state
from .storage import get_or_create_capture_group, group_dir
from .broadcast import read_selected_data

# Kept for anything importing it; the live matching lives in consoles.py.
PATH_RE = consoles.EMBLEM_PATH_RE

# What we've actually seen on the wire, surfaced in the control panel so a user
# whose console isn't being picked up can see whether emblem traffic is
# reaching the proxy at all, and on which host.
detected = {
    "emblem_host": None,     # host the last emblem request went to
    "console_guess": None,   # console that hostname belongs to, if recognisable
    "last_seen": None,       # when, as HH:MM:SS
    "requests": 0,           # emblem requests handled this run
    "other_demonware": [],   # demonware hosts seen that were NOT emblem traffic
}
_detected_lock = threading.Lock()

# Set if the proxy couldn't start at all, so the control panel can say so
# instead of the user assuming their console settings are wrong.
startup_error = None


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def _note_emblem_host(host):
    with _detected_lock:
        if detected["emblem_host"] != host:
            guess = consoles.guess_console_from_host(host)
            detected["emblem_host"] = host
            detected["console_guess"] = guess
            named = f" ({guess.upper()})" if guess else ""
            log(f"  emblem endpoint detected: {host}{named}")
        detected["last_seen"] = time.strftime("%H:%M:%S")
        detected["requests"] += 1


def _note_other_demonware(host):
    """Record a Demonware host that wasn't emblem traffic. True the first time
    each host shows up, so the caller logs it once instead of every request."""
    with _detected_lock:
        seen = detected["other_demonware"]
        if host in seen or len(seen) >= 20:
            return False
        seen.append(host)
        return True


def get_detected():
    with _detected_lock:
        return dict(detected, other_demonware=list(detected["other_demonware"]))


def pipe(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _tunnel(client, upstream):
    """Splice two sockets together until either end goes away.

    Both sockets go back to blocking with no timeout first: a tunnel can sit
    idle for minutes at a time during matchmaking, and a timeout here would
    tear down a perfectly healthy PSN connection.
    """
    client.settimeout(None)
    upstream.settimeout(None)
    t1 = threading.Thread(target=pipe, args=(upstream, client), daemon=True)
    t2 = threading.Thread(target=pipe, args=(client, upstream), daemon=True)
    t1.start(); t2.start()
    t1.join(); t2.join()
    # shutdown() alone leaves the descriptors open until the garbage collector
    # gets to them. Every passed-through request goes through here, and a
    # console makes a lot of them, so they have to be closed explicitly - macOS
    # gives an app launched from Finder only 256 descriptors to work with.
    try:
        upstream.close()
    except OSError:
        pass


def _connect_upstream(host, port):
    sock = socket.create_connection((host, port), timeout=config.CONNECT_TIMEOUT)
    return sock


def recv_full_response(sock):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    header_end = data.find(b"\r\n\r\n")
    if header_end == -1:
        return data, b""
    header_end += 4
    headers = data[:header_end]
    body = data[header_end:]
    cl = None
    for line in headers.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                cl = int(line.split(b":", 1)[1].strip())
            except ValueError:
                cl = None
            break
    if cl is not None:
        while len(body) < cl:
            chunk = sock.recv(4096)
            if not chunk:
                break
            body += chunk
    return headers, body


def fetch_real(req, host, port):
    upstream = _connect_upstream(host, port)
    try:
        upstream.settimeout(config.READ_TIMEOUT)
        upstream.sendall(req)
        return recv_full_response(upstream)
    finally:
        upstream.close()


def _req_header(req, name):
    """Return the value of an HTTP request header (case-insensitive) or None."""
    needle = (name.lower() + ":").encode()
    for line in req.split(b"\r\n")[1:]:
        if not line:
            break
        if line.lower().startswith(needle):
            return line.split(b":", 1)[1].strip().decode("latin1", "replace")
    return None


def handle_target_request(client, req, host, port, path, userhash, slot_num):
    mode = read_state()
    _note_emblem_host(host)

    if mode == "INJECT":
        selected = read_selected_data()
        if selected is not None:
            client.sendall(selected)
            # A conditional/cache-check request from the console is the main
            # reason Show mode can silently appear to do nothing - your console
            # already has a cached copy of one of your slots and may not ask
            # again right away. Nothing to fix here, just worth noting.
            if _req_header(req, "If-None-Match") or _req_header(req, "If-Modified-Since") or _req_header(req, "Range"):
                log(f"  Show: sent selected emblem for slot_{slot_num}, but the console sent a "
                    "cache-check request - it may keep using its cached copy instead")
            else:
                log(f"  Show: sent selected emblem for slot_{slot_num} ({len(selected)} bytes)")
            return
        log("  Show mode is on but no emblem is selected - passing real data through")

    headers, body = fetch_real(req, host, port)

    if mode == "CAPTURE":
        group = get_or_create_capture_group(userhash)
        with open(os.path.join(group_dir(group), f"slot_{slot_num}.bin"), "wb") as f:
            f.write(headers + body)
        log(f"  Captured: group {group} slot_{slot_num} ({len(body)} bytes)")

    client.sendall(headers + body)


def _split_request_target(url, req):
    """Work out (host, port, path) for a proxied request.

    Proxies normally get the absolute form ("GET http://host/path HTTP/1.1"),
    but the origin form with a Host header is legal and some clients send it.
    The original code assumed absolute form and produced an empty host for the
    other one, which silently broke those requests.
    """
    if "://" in url:
        rest = url.split("://", 1)[1]
        host_port, _, path = rest.partition("/")
        path = "/" + path
    else:
        host_port = _req_header(req, "Host") or ""
        path = url if url.startswith("/") else "/" + url
    host, _, port = host_port.partition(":")
    try:
        port = int(port) if port else 80
    except ValueError:
        port = 80
    return host, port, path


def handle(client):
    try:
        client.settimeout(config.READ_TIMEOUT)
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = client.recv(4096)
            if not chunk:
                client.close()
                return
            req += chunk
        line = req.split(b"\r\n", 1)[0].decode("latin1")
        parts = line.split()
        if len(parts) < 2:
            client.close()
            return
        method = parts[0].upper()

        if method == "CONNECT":
            host, _, port = parts[1].partition(":")
            try:
                port = int(port) if port else 443
            except ValueError:
                port = 443
            if consoles.is_demonware(host) and _note_other_demonware(host):
                log(f"  note: HTTPS traffic to {host} - tunneled untouched, never decrypted")
            upstream = _connect_upstream(host, port)
            client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            _tunnel(client, upstream)
        else:
            host, port, path = _split_request_target(parts[1], req)
            if not host:
                client.close()
                return

            rest_of_req = req.split(b"\r\n", 1)[1]
            new_line = f"{method} {path} HTTP/1.1\r\n".encode("latin1")
            req_rewritten = new_line + rest_of_req

            console_key = settings.get_console()
            userhash, slot_num = consoles.match_emblem_request(host, path, console_key)

            if slot_num is not None:
                handle_target_request(client, req_rewritten, host, port, path, userhash, slot_num)
            else:
                if consoles.is_demonware(host) and _note_other_demonware(host):
                    log(f"  note: HTTP request to {host} - not emblem traffic, passed through untouched")
                upstream = _connect_upstream(host, port)
                upstream.sendall(req_rewritten)
                _tunnel(client, upstream)
    except Exception as e:
        log(f"  error: {e}")
    finally:
        try:
            client.close()
        except OSError:
            pass


def serve(host=None, port=None):
    """Run the proxy loop. Blocks forever - call from a dedicated thread."""
    global startup_error
    from .state import write_state
    host = host or config.PROXY_HOST
    port = port or config.PROXY_PORT
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Anything that goes wrong before the accept loop kills this thread, and a
    # dead proxy thread looks exactly like a misconfigured console - nothing
    # happens, with no explanation. So failures are recorded where the control
    # panel can show them, which is the only channel a packaged app has.
    try:
        if not os.path.exists(config.STATE_FILE):
            write_state("PASSTHROUGH")
        srv.bind((host, port))
    except OSError as e:
        if getattr(e, "filename", None):
            startup_error = (
                f"The proxy couldn't write to {e.filename} ({e.strerror or e}). "
                f"Check that {config.ROOT_DIR} exists and is writable."
            )
        else:
            startup_error = (
                f"The proxy couldn't listen on port {port} ({e.strerror or e}). "
                f"Something else is probably using it. Stop that program, or restart "
                f"with BO2_PROXY_PORT set to a free port."
            )
        log(f"  ERROR: {startup_error}")
        srv.close()
        return
    srv.listen(200)
    console = consoles.get(settings.get_console())
    log(f"Proxy listening on {host}:{port}  mode={read_state()}  console={console.name}")
    while True:
        client, _ = srv.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()
