"""Which console is on the other end, and how to recognise its emblem traffic.

Black Ops II shipped in 2012 on PS3, Xbox 360, Wii U and PC, and was later
re-released on PS4 and PS5 as ports of the PS3 build. Those ports talk to the
same legacy Demonware backend, which is why emblems still copy between them.

The catch is that the content-server *hostname* is per-SKU and isn't published
anywhere. Pinning one hostname (this tool originally hardcoded the PS3 one,
which is also what the PS5 port happens to use) means the proxy silently does
nothing the moment a different SKU is in play. There is no way to know the
PS4 port's hostname without capturing it from a PS4.

So detection keys off the request *path* instead. Demonware emblem storage
objects are always ".../u<hex>.slot_<n>", which is distinctive enough to
identify on its own, on any host. A plain-HTTP request to a demonware.net host
whose path looks like that is an emblem request, whatever console sent it.

Hostnames are still listed per console, for three reasons: the control panel
can show you what it expects, `guess_console_from_host` can name the console
that actually connected, and anyone who wants belt-and-braces behaviour can
pin a specific host in the control panel instead of using auto.
"""
import re

# ".../u51b08745d269.slot_504?..." -> (userhash, slot number). This is the
# real signature of an emblem request and the basis of auto-detection.
EMBLEM_PATH_RE = re.compile(r"/(u[0-9a-fA-F]+)\.slot_(\d+)")

# Any Demonware host. Emblem traffic only ever goes here, so this bounds what
# auto-detection is willing to look at - no other host is ever inspected.
DEMONWARE_HOST_RE = re.compile(r"(?:^|\.)demonware\.net$", re.IGNORECASE)

# BO2 content servers follow "ops2-<platform>-cs[<n>].prod.demonware.net".
# Used to name an unrecognised-but-plausible host in the log.
BO2_HOST_RE = re.compile(r"^ops2-([a-z0-9]+)-cs\d*\.prod\.demonware\.net$", re.IGNORECASE)

# The PS3 content server. The 2012 PS3 release and the PS4/PS5 ports of that
# build are all known or expected to use it, since the ports kept the PS3
# backend (that is exactly why emblems copy across those three).
LEGACY_PS_HOST = "ops2-ps3-cs.prod.demonware.net"


class Console:
    """A console preset: what to expect on the wire, and how to set the
    proxy up on that hardware."""

    def __init__(self, key, name, hosts=(), proxy_steps=(), note=""):
        self.key = key
        self.name = name
        self.hosts = tuple(hosts)
        self.proxy_steps = tuple(proxy_steps)
        self.note = note

    def as_dict(self):
        return {
            "key": self.key,
            "name": self.name,
            "hosts": list(self.hosts),
            "proxy_steps": list(self.proxy_steps),
            "note": self.note,
        }


_PS5_STEPS = (
    "Settings → Network → Settings → Set Up Internet Connection",
    "Highlight your network, press the Options button, choose Advanced Settings",
    "Set Proxy Server to Use",
    "Enter the address and port shown above",
    "Save, then run Test Internet Connection",
)

_PS4_STEPS = (
    "Settings → Network → Set Up Internet Connection",
    "Pick Use Wi-Fi or Use a LAN Cable, then choose Custom (not Easy — Easy skips the proxy screen)",
    "IP Address Settings: Automatic · DHCP Host Name: Do Not Specify · DNS Settings: Automatic · MTU Settings: Automatic",
    "Proxy Server: Use, then enter the address and port shown above",
    "Save, then run Test Internet Connection",
)

_XBOX_STEPS = (
    "Settings → General → Network settings → Advanced settings",
    "Xbox has no proxy field — set up this PC's connection sharing or a DNS/gateway route to it instead",
    "See docs/CONSOLES.md for the workaround",
)

_PC_STEPS = (
    "Set the system proxy to the address and port shown above",
    "Windows: Settings → Network & Internet → Proxy → Manual proxy setup",
    "macOS: System Settings → Network → your connection → Details → Proxies → Web Proxy (HTTP)",
)

CONSOLES = {
    "auto": Console(
        key="auto",
        name="Auto-detect",
        hosts=(),
        proxy_steps=(
            "Point your console's proxy setting at the address and port shown above",
            "Pick your console from the list to see its exact menu path",
        ),
        note="Recognises emblem traffic by its request path, so it works with any "
             "console or SKU. This is the recommended setting.",
    ),
    "ps5": Console(
        key="ps5",
        name="PlayStation 5",
        hosts=(LEGACY_PS_HOST,),
        proxy_steps=_PS5_STEPS,
        note="The PS5 port of BO2 uses the legacy PS3 content server.",
    ),
    "ps4": Console(
        key="ps4",
        name="PlayStation 4",
        hosts=(LEGACY_PS_HOST, "ops2-ps4-cs.prod.demonware.net"),
        proxy_steps=_PS4_STEPS,
        note="The PS4 port is the same port of the PS3 build as the PS5 one, so it "
             "is expected on the legacy PS3 content server. Its own hostname is "
             "listed too in case Activision split the SKUs. If neither matches, "
             "use Auto-detect — it does not care about the hostname.",
    ),
    "ps3": Console(
        key="ps3",
        name="PlayStation 3",
        hosts=(LEGACY_PS_HOST,),
        proxy_steps=(
            "Settings → Network Settings → Internet Connection Settings → Custom",
            "Accept the defaults until the Proxy Server screen",
            "Proxy Server: Use, then enter the address and port shown above",
            "Save, then test the connection",
        ),
        note="Emblem data written by a PS3 is big-endian; the renderer detects "
             "that on its own.",
    ),
    "xbox": Console(
        key="xbox",
        name="Xbox 360 / Xbox One / Series",
        hosts=("ops2-xbl-cs.prod.demonware.net", "ops2-xbox-cs.prod.demonware.net"),
        proxy_steps=_XBOX_STEPS,
        note="Xbox consoles have no proxy setting, so this needs a routing "
             "workaround rather than a proxy field. Untested.",
    ),
    "pc": Console(
        key="pc",
        name="PC",
        hosts=("ops2-pc-cs.prod.demonware.net",),
        proxy_steps=_PC_STEPS,
        note="Untested — the PC release was delisted, but the endpoint layout is "
             "the same.",
    ),
}

DEFAULT_CONSOLE = "auto"


def get(key):
    """The Console preset for `key`, falling back to auto for anything unknown."""
    return CONSOLES.get((key or "").lower(), CONSOLES[DEFAULT_CONSOLE])


def all_consoles():
    """Every preset, auto first, for the control panel's picker."""
    order = ["auto", "ps5", "ps4", "ps3", "xbox", "pc"]
    return [CONSOLES[k].as_dict() for k in order if k in CONSOLES]


def is_demonware(host):
    return bool(DEMONWARE_HOST_RE.search((host or "").split(":")[0].strip()))


def guess_console_from_host(host):
    """Name the console a hostname belongs to, or None.

    Matches the pinned host lists first, then falls back to reading the
    platform token out of an "ops2-<platform>-cs" style hostname, so a SKU
    nobody has seen yet still gets named rather than reported as unknown.
    """
    host = (host or "").split(":")[0].strip().lower()
    if not host:
        return None
    for key in ("ps5", "ps4", "ps3", "xbox", "pc"):
        if host in (h.lower() for h in CONSOLES[key].hosts):
            # LEGACY_PS_HOST is shared by three presets; the first match (ps5)
            # would be arbitrary, so report the platform token instead.
            if host == LEGACY_PS_HOST.lower():
                return "ps3"
            return key
    m = BO2_HOST_RE.match(host)
    if m:
        token = m.group(1).lower()
        return {"xbl": "xbox", "xbox": "xbox"}.get(token, token)
    return None


def match_emblem_request(host, path, console_key=DEFAULT_CONSOLE):
    """Decide whether this plain-HTTP request is a BO2 emblem fetch.

    Returns (userhash, slot_number) when it is, or (None, None).

    Auto mode accepts any demonware.net host whose path carries the emblem
    object pattern. A pinned console accepts only its own hostnames, so it
    behaves exactly like the original hardcoded check.
    """
    host = (host or "").split(":")[0].strip()
    m = EMBLEM_PATH_RE.search(path or "")
    if not m:
        return None, None

    console = get(console_key)
    if console.key == DEFAULT_CONSOLE:
        if not is_demonware(host):
            return None, None
    else:
        if host.lower() not in (h.lower() for h in console.hosts):
            return None, None

    return m.group(1), int(m.group(2))
