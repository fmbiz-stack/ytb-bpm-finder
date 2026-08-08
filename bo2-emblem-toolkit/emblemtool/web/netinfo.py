"""Best-effort LAN IP detection, so the web UI can tell the user exactly
what to type into their console's proxy settings without opening a terminal.

One address isn't enough. The interface that reaches the internet is often not
the one the console is on: a Mac sharing its connection to a console over
Wi-Fi or Ethernet puts that console on bridge100 at 192.168.2.x while the
default route goes out over something else entirely, and Windows mobile
hotspots do the same thing. So the outbound-route address is offered first,
and every other private address on the machine is listed after it.
"""
import re
import socket
import subprocess
import sys

# Interfaces that exist to serve a directly-attached device - a console tethered
# to this machine will be on one of these, and it's the address it needs.
_SHARING_HINTS = {
    "bridge": "Internet Sharing / bridge",
    "ap": "access point",
    "wlan": "Wi-Fi",
    "en": "Ethernet or Wi-Fi",
    "eth": "Ethernet",
}


def get_lan_ip():
    """Return this machine's LAN IP as seen by outbound traffic, or None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send anything (UDP, no handshake) - just asks the
        # OS routing table which local interface/IP would be used to reach
        # an external address.
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _is_private(ip):
    if ip.startswith("10.") or ip.startswith("192.168."):
        return True
    if ip.startswith("172."):
        try:
            return 16 <= int(ip.split(".")[1]) <= 31
        except (IndexError, ValueError):
            return False
    return False


def _is_usable(ip):
    return (
        bool(ip)
        and not ip.startswith("127.")
        and not ip.startswith("169.254.")  # link-local: never routable to a console
        and ip != "0.0.0.0"
    )


def _run(cmd):
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5,
            stdin=subprocess.DEVNULL,
        )
        return out.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _interface_addresses():
    """[(interface, ipv4), ...] for every interface, best effort per OS."""
    pairs = []

    if sys.platform == "darwin" or "bsd" in sys.platform:
        # ifconfig blocks are "en0: flags=..." followed by indented "inet x.x.x.x"
        current = None
        for line in _run(["ifconfig"]).splitlines():
            m = re.match(r"^(\S+):", line)
            if m:
                current = m.group(1)
                continue
            m = re.search(r"^\s+inet (\d+\.\d+\.\d+\.\d+)", line)
            if m and current:
                pairs.append((current, m.group(1)))

    elif sys.platform.startswith("linux"):
        for line in _run(["ip", "-4", "-o", "addr", "show"]).splitlines():
            m = re.match(r"^\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                pairs.append((m.group(1), m.group(2)))
        if not pairs:  # very old or minimal systems without iproute2
            current = None
            for line in _run(["ifconfig"]).splitlines():
                m = re.match(r"^(\S+)", line)
                if m and not line.startswith((" ", "\t")):
                    current = m.group(1).rstrip(":")
                m = re.search(r"inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)", line)
                if m and current:
                    pairs.append((current, m.group(1)))

    elif sys.platform == "win32":
        current = None
        for line in _run(["ipconfig"]).splitlines():
            if line and not line.startswith(" "):
                current = line.strip().rstrip(":")
                continue
            m = re.search(r"IPv4 Address[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                pairs.append((current or "network adapter", m.group(1)))

    if not pairs:
        # Last resort - misses most interfaces on macOS but costs nothing.
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                pairs.append(("", info[4][0]))
        except (OSError, socket.gaierror):
            pass

    return [(iface, ip) for iface, ip in pairs if _is_usable(ip)]


def _label_for(iface, ip, is_primary):
    if is_primary:
        return "this machine's main network — try this one first"
    lowered = (iface or "").lower()
    for hint, text in _SHARING_HINTS.items():
        if lowered.startswith(hint):
            base = f"{iface} ({text})"
            break
    else:
        base = iface or "other interface"
    if not _is_private(ip):
        return f"{base} — public address, almost certainly not the one"
    if lowered.startswith("bridge"):
        return f"{base} — use this if the console is tethered to this machine"
    return base


def get_lan_ips():
    """Every address a console could plausibly be told to use, best first.

    Returns [{"ip", "interface", "label", "primary"}, ...].
    """
    primary = get_lan_ip()
    seen = {}

    if _is_usable(primary):
        seen[primary] = {
            "ip": primary,
            "interface": "",
            "label": _label_for("", primary, True),
            "primary": True,
        }

    for iface, ip in _interface_addresses():
        if ip in seen:
            if not seen[ip]["interface"]:
                seen[ip]["interface"] = iface
            continue
        seen[ip] = {
            "ip": ip,
            "interface": iface,
            "label": _label_for(iface, ip, False),
            "primary": False,
        }

    entries = list(seen.values())
    # Primary first, then private addresses, then anything else.
    entries.sort(key=lambda e: (not e["primary"], not _is_private(e["ip"]), e["ip"]))
    return entries
