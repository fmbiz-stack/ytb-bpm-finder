# Installing the BO2 Emblem Toolkit

This is a one-time setup on your computer. Once it's done, point your console
at it ([docs/CONSOLES.md](CONSOLES.md)) and day-to-day use is just
[docs/USAGE.md](USAGE.md).

- [Windows](#windows)
- [macOS](#macos)
- [Linux](#linux)
- [Running from source on any OS](#running-from-source-on-any-os)
- [Troubleshooting](#troubleshooting)

## Windows

Grab `BO2EmblemToolkit.exe` from the
[Releases page](https://github.com/alexkotr1/bo2-emblem-toolkit/releases).
It's a single file with everything already inside it. Put it in its own folder
(it saves your captured emblems next to itself), double-click it, and skip
ahead to [docs/CONSOLES.md](CONSOLES.md).

Windows may warn you that the file is from an unrecognized publisher, since it
isn't signed with a paid code-signing certificate. Click "More info" then "Run
anyway." If you'd rather verify the code yourself first, use the source setup
below.

The first time it runs, Windows Firewall will ask whether to allow it. Say yes
for **private networks** — your console can't reach the proxy otherwise.

## macOS

Grab `BO2EmblemToolkit.app` from the
[Releases page](https://github.com/alexkotr1/bo2-emblem-toolkit/releases), or
[run it from source](#running-from-source-on-any-os) — on macOS that's as
simple as double-clicking `start.command`, and it avoids all of the Gatekeeper
business below.

### Gatekeeper

The app isn't notarised (that needs a paid Apple Developer account), so macOS
will refuse to open it on the first try and say it's damaged or from an
unidentified developer. It isn't damaged — that's the standard message for
anything downloaded without notarisation. Clear the quarantine flag:

```
xattr -dr com.apple.quarantine /Applications/BO2EmblemToolkit.app
```

then open it normally. Alternatively, right-click the app, choose Open, and
click Open in the dialog — that works on some macOS versions but not all
recent ones.

### The firewall prompt

The first time it runs, macOS asks whether to allow incoming connections.
**Allow** it. Your console connects *in* to the proxy, so denying this is the
same as not running the tool at all. If you clicked Deny by accident:

System Settings → Network → Firewall → Options, find the entry, set it to
"Allow incoming connections". If there's no entry, remove and re-add it with
the `+` button.

### Where the app keeps your emblems

The `.app` writes captures to:

```
~/Library/Application Support/BO2EmblemToolkit
```

Not inside the app bundle — anything in there is thrown away when you replace
the app. If you'd rather keep it portable, make a folder named `saved` next to
the `.app` and it will use that folder instead.

### Stopping it

The `.app` has no terminal window, so use the **Quit** button in the control
panel. If you run from source or use the command-line binary, `Ctrl+C` in the
terminal works too.

### Building the mac app yourself

```
./build_macos.sh
```

That produces `dist/app/BO2EmblemToolkit.app` and a plain command-line binary
at `dist/cli/BO2EmblemToolkit`. Both are ad-hoc signed. The build targets
whichever architecture your Python is; see the note the script prints for
universal (Intel + Apple Silicon) builds.

## Linux

Run from source — see below. `./start.sh` is a convenience wrapper around
`python3 run.py`.

If your firewall is active, allow inbound TCP on port 8080, e.g.
`sudo ufw allow from 192.168.0.0/16 to any port 8080 proto tcp`.

## Running from source on any OS

### 1. Install Python

You need Python 3.9 or newer.

- **Windows**: [python.org/downloads](https://www.python.org/downloads/). During
  installation, check "Add python.exe to PATH". It's easy to miss, and nothing
  here will run without it.
- **macOS**: often already there. If not, `brew install python3` or python.org.
- **Linux**: your distro's package manager, e.g. `sudo apt install python3 python3-pip`.

Check it worked:

```
python3 --version
```

You should see something like `Python 3.11.4`.

### 2. Get the toolkit

Download or clone this repository, then open a terminal **in that folder**.

### 3. Install the one dependency

```
pip install -r requirements.txt
```

This installs [Pillow](https://pypi.org/project/Pillow/), used to render
emblem thumbnails. Nothing else is required.

### 4. Run it

- **Windows**: double-click `start.bat`
- **macOS**: double-click `start.command` (it installs Pillow for you if it's missing)
- **Linux**: `./start.sh`
- **Anywhere**: `python3 run.py`

A terminal window will show something like:

```
================================================================
 BO2 Emblem Toolkit
================================================================
 Control panel  : http://localhost:8090
 Console        : Auto-detect
 Proxy setting  : 192.168.1.42 : 8080
                  or 192.168.2.1 (bridge100)
 Saving data to : /Users/you/bo2-emblem-toolkit
================================================================
```

Your browser should open to the control panel automatically. If it doesn't,
open `http://localhost:8090` yourself.

Keep this terminal window open while you use the toolkit. Closing it stops
everything. To stop on purpose, press `Ctrl+C` in that window, or use the Quit
button in the control panel.

Next: [point your console at it](CONSOLES.md).

## Troubleshooting

**Console says "no internet connection" after setting the proxy**

- Check the console and this computer really are on the same network. If the
  console is connected to this computer's hotspot or Internet Sharing, use
  *that* interface's address, not your main router-facing one. The control
  panel lists every address it found — the sharing one is usually
  `192.168.2.1` on macOS and `192.168.137.1` on Windows.
- Your firewall may be blocking the connection:
  - **Windows**: allow inbound TCP on port 8080 for Python, or add a rule in an
    elevated PowerShell:
    ```
    New-NetFirewallRule -DisplayName "BO2 Emblem Toolkit" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
    ```
  - **macOS**: System Settings → Network → Firewall → Options, and allow
    incoming connections for Python or BO2EmblemToolkit.
- If you use an ad-blocking DNS service, it may be blocking PlayStation's own
  telemetry domains, unrelated to this tool but easy to mistake for it.
  Switching to a normal DNS resolver (e.g. 1.1.1.1) resolves this.

**The control panel doesn't show a LAN IP, or shows the wrong one**

The panel lists every address it can find, with the outbound-route one first.
If none of them work, or the list is empty, find it yourself:

- Windows: `ipconfig`
- macOS: `ipconfig getifaddr en0`, or `ifconfig` for the full list
- Linux: `ip addr`

Look for the adapter on the same network as your console.

**"Address already in use" / the panel shows a proxy error**

Something else on this computer already holds port 8080 or 8090. Either stop
it, or run the toolkit on different ports:

```
BO2_PROXY_PORT=8081 BO2_WEB_PORT=8091 python3 run.py
```

on Windows:

```
set BO2_PROXY_PORT=8081 && set BO2_WEB_PORT=8091 && python run.py
```

Whatever you set `BO2_PROXY_PORT` to is what your console's proxy setting needs
to say. The control panel's port moves on its own if it has to; the proxy's
never does, since your console is configured with it by hand.

**"python is not recognized" / "command not found"**

Python isn't on your PATH. Reinstall it and check "Add to PATH" during setup
(Windows), or use `python3` instead of `python` (macOS/Linux).

**macOS: "Operation not permitted" or the app won't launch at all**

Usually quarantine — see [Gatekeeper](#gatekeeper) above. If it still won't
launch, run the command-line binary from Terminal instead
(`dist/cli/BO2EmblemToolkit`), which prints the actual error.
