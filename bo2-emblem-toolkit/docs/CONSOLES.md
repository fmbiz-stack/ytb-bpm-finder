# Pointing your console at the toolkit

The toolkit has to be [installed and running](INSTALL.md) first. The control
panel shows the address and port to use, and repeats the steps below for
whichever console you pick from the list at the top of it.

Your console and the computer need to be on the same network — the same
Wi-Fi/router, or the computer's own hotspot / Internet Sharing with the console
connected to it.

## Which console setting to use

Leave it on **Auto-detect** unless you have a reason not to. Emblem requests
are recognised by their path (`/u<hex>.slot_<n>`) on a Demonware host, which
doesn't depend on knowing your console's hostname in advance. Picking a
specific console only narrows what the proxy will touch, and changes which
setup steps the panel shows you.

Once traffic starts flowing, the panel's "Console setup" section tells you what
it actually saw — the endpoint hostname and which console it belongs to.

## PlayStation 5

1. Settings → Network → Settings → Set Up Internet Connection
2. Highlight your network, press the Options button, choose Advanced Settings
3. Set Proxy Server to **Use**
4. Enter the address and port from the control panel
5. Save, then run Test Internet Connection

## PlayStation 4

1. Settings → Network → Set Up Internet Connection
2. Choose Use Wi-Fi or Use a LAN Cable
3. Choose **Custom** — Easy skips the proxy screen entirely, which is the most
   common reason people can't find the setting
4. Work through the screens:
   - IP Address Settings: **Automatic**
   - DHCP Host Name: **Do Not Specify**
   - DNS Settings: **Automatic**
   - MTU Settings: **Automatic**
   - Proxy Server: **Use**
5. Enter the address and port from the control panel
6. Save, then run Test Internet Connection

The PS4 test result normally reads "Successful" for the connection and may show
NAT Type 2 or 3. If PSN sign-in fails but the connection succeeds, see
[Troubleshooting](#troubleshooting).

## PlayStation 3

1. Settings → Network Settings → Internet Connection Settings
2. Choose **Custom**
3. Accept the defaults through the screens until you reach Proxy Server
4. Proxy Server: **Use**, then enter the address and port from the control panel
5. Save and test the connection

Emblem data written by a PS3 is big-endian, unlike the PS4/PS5 releases. The
renderer works that out per capture, so PS3 captures and PS4/PS5 captures show
up correctly side by side in the same panel.

## Xbox 360 / Xbox One / Series

Xbox consoles have no proxy setting, so there's no direct equivalent. This is
untested, but the shape of the workaround is to make the console route its
traffic through your computer instead of asking it to:

- Share your computer's connection to the console (Internet Connection Sharing
  on Windows, Internet Sharing on macOS) and redirect port 80 to the proxy with
  a firewall rule, or
- Run a DNS server that points the Demonware content host at your computer, and
  set the console's DNS manually.

If you get either working, the toolkit itself needs no changes — pick
Auto-detect and it will pick the traffic up. An issue or PR describing what
worked would be welcome.

## PC

Set the system proxy to the address and port shown in the control panel:

- Windows: Settings → Network & Internet → Proxy → Manual proxy setup
- macOS: System Settings → Network → your connection → Details → Proxies → Web Proxy (HTTP)

Untested, since the PC release was delisted, but the endpoint layout is the
same.

## When you're finished

Set the proxy setting back to **Do Not Use** on the console. If you leave it
pointing at a computer that isn't running the toolkit, the console loses its
internet connection and the cause is not obvious later.

## Troubleshooting

**The connection test fails, or the console says it has no internet**

The address is the usual culprit. If the console is tethered to this computer
rather than sharing a router with it, you need that interface's address —
`192.168.2.1` on macOS Internet Sharing, `192.168.137.1` on a Windows mobile
hotspot — not the one facing your own router. The control panel lists all of
them; try the others.

After that, check the firewall on the computer. See
[INSTALL.md](INSTALL.md#troubleshooting).

**The console connects, but nothing shows up in the control panel**

Open the "Console setup" section of the panel. It tells you which of these
you're in:

- *waiting for emblem traffic* — nothing has reached the proxy at all. The
  address, port or firewall is wrong.
- *console connected, no emblem traffic yet* — the network side is right, the
  game just hasn't asked for an emblem yet. Open a player's profile in Capture
  mode, or your own emblem editor in Show mode.
- *emblem traffic seen* — it's working. If captures still aren't appearing,
  you're in the wrong mode.

**PSN sign-in fails while the proxy is on**

Sign-in is HTTPS and is tunneled without being touched, so this is normally a
network problem rather than the proxy rewriting anything. Check that the
computer itself has a working connection, and that no VPN on the computer is
re-routing the tunneled traffic somewhere the console's session doesn't expect.
