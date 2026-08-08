# macOS and PS4 support — what changed and why

Notes for @alexkotr1 on this branch. Everything here is on top of v1.0.0, it's
MIT like the rest, and it's yours to take, split up, or ignore. Nothing about
the emblem format, the shape calibration or the renderer's geometry was
touched — that work is all still exactly as you had it.

Test suite: `python -m unittest discover -s tests` (43 tests, stdlib only,
Pillow-dependent ones skip without it).

## PS4

**The hostname was the blocker.** `config.TARGET_HOST_SUBSTR` pinned
`ops2-ps3-cs.prod.demonware.net`. That's the right host for the PS5 release —
it's a port of the PS3 build and kept the PS3 backend — but nothing guarantees
Activision shipped the PS4 SKU on the same one, and there's no way to find out
without a PS4 to capture from. Pinned to one hostname, the failure mode is
silent: the proxy passes everything through and the user sees nothing happen.

So matching now keys off the request path instead. Demonware emblem objects are
always `/u<hex>.slot_<n>`, which is distinctive on its own, and the check is
bounded to `*.demonware.net` so nothing else is ever inspected. That works on
any console and any SKU without knowing its hostname in advance
(`emblemtool/consoles.py`).

The hostname lists are still there per console, so you can pin one if you'd
rather, and so the panel can name what it saw. If the PS4 does turn out to use
its own host, this already handles it and the preset list just needs the name
filled in for tidiness.

**Endianness.** `parse_slot_bytes` was hardcoded to `<`. The PS3 is big-endian
PowerPC; PC and the PS4/PS5 ports are little-endian x86. A PS3 capture parsed as
little-endian renders as garbage. `detect_endianness` scores both orders against
the ranges the fields can't leave (colours 0..1, finite floats, plausible shape
ids) and picks the better one, per blob — so PS3 and PS4/PS5 captures sit in the
same panel and both render. Verified: the same emblem encoded big- and
little-endian renders to byte-identical PNGs.

**Console picker** in the control panel (auto / PS5 / PS4 / PS3 / Xbox / PC),
persisted in `settings.json`. Mostly it just shows the right menu path for the
hardware — the PS4's proxy field is behind **Custom** setup, which is the single
most common "I can't find the proxy setting" complaint — but it also lets
someone pin a host if they want the old narrow behaviour.

**Detection feedback**, which turned out to matter more than expected. The panel
now distinguishes "nothing is reaching the proxy" from "traffic is arriving but
no emblem request yet" from "emblem traffic seen, here's the endpoint and which
console it looks like". Previously all three looked like "nothing happens", and
so did a wrong IP, a firewall block and the wrong mode.

## macOS

**The `.app` data directory.** A frozen build wrote next to `sys.executable`.
Inside a `.app` that's `Contents/MacOS/`, which is invisible in Finder and
thrown away when the app is replaced — captures would silently vanish on
upgrade. macOS bundles now use `~/Library/Application Support/BO2EmblemToolkit`.
Windows behaviour is unchanged, and an existing `saved/` beside the executable
still wins everywhere, so nobody's captures move.

**A missing data directory crashed the proxy thread**, which is the normal
first-run state for that Application Support path. `write_state` threw
`FileNotFoundError` inside the thread, the thread died, and the app carried on
looking healthy with no proxy. Directory is created at import now, and any
startup failure is recorded and shown in the panel instead of vanishing.

**Socket leak.** `pipe()` called `shutdown()` but never `close()`, so every
passed-through request leaked two descriptors until GC. It's survivable on
Windows; a Finder-launched macOS app gets a 256-descriptor soft limit, and a
console makes a lot of requests. Closed explicitly now, and `run.py` raises the
soft limit toward the hard one where the OS allows it. (Confirmed with
`-W error::ResourceWarning` in the test run.)

**Launchers and packaging**: `start.command` for Finder (finds a suitable
Python, installs Pillow if it's missing), `start.sh` for Linux, and
`build_macos.sh` producing both a `.app` and a plain CLI binary, ad-hoc signed.
Not notarised, so `docs/INSTALL.md` covers the quarantine flag and the incoming
-connections firewall prompt.

**A Quit button**, because the `.app` has no terminal to Ctrl+C.

**LAN IP detection** returned one address, from the outbound route. That's the
wrong one whenever the console is tethered to the machine rather than sharing a
router — which on a Mac means Internet Sharing, where the console is on
`bridge100` at 192.168.2.1 and the default route goes somewhere else entirely.
It now lists every usable address with the outbound one first, labels the
sharing interfaces, and the panel and terminal banner show all of them.

## Things that aren't macOS or PS4, found on the way

Say the word and I'll pull these into their own PR instead.

- **Path traversal in the control panel.** `group` came out of the URL and went
  into `os.path.join` unvalidated, on a server bound to `0.0.0.0` because the
  console has to reach it. `/api/emblems/<group>/<slot>/label` would write
  `meta.json` anywhere the process could reach, and `/api/render/` would read
  back out. Group names are validated in `group_dir()` now — one chokepoint,
  everything routes through it — plus at the request handlers. Tests cover it.
- **Origin-form requests.** `handle` assumed the absolute form
  (`GET http://host/path`). The origin form with a `Host` header is legal, and
  produced an empty host and a dead request. Falls back to the header now.
- **No socket timeouts.** A wedged connection parked a thread forever. Connect
  and read timeouts added; tunnels deliberately keep none, since an idle
  matchmaking tunnel is normal and a timeout there would break PSN.
- **Port conflicts.** The panel now moves to the next free port if 8090 is
  taken (nothing external points at it), while the proxy port deliberately
  doesn't — the console is configured with that by hand — and instead fails
  loudly in the panel. `BO2_PROXY_PORT` / `BO2_WEB_PORT` / `BO2_TOOLKIT_DATA_DIR`
  override the defaults.
- `Image.new` and `point()` could throw on colour values slightly outside 0..1;
  clamped.
- `int()` on a malformed `Content-Length` could throw; guarded.

## What I couldn't test

I don't have a PS4, a PS5 or a PS3, so none of this has touched real console
traffic. What is tested is everything up to the socket: 43 tests including
capture and Show driven end-to-end through the real proxy over real sockets
against a stand-in Demonware server, covering the legacy PS3 host, an unknown
PS4-style host, non-emblem Demonware paths and unrelated hosts.

The specific thing worth confirming on hardware is what the PS4 release's
content-server hostname actually is. Auto-detect doesn't need it, but it's
worth knowing, and the panel prints it as soon as any emblem request comes
through.
