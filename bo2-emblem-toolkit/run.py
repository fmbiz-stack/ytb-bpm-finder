#!/usr/bin/env python3
"""Start the BO2 Emblem Toolkit.

This is the only thing you ever need to run. It starts the network proxy
and the web control panel together, then opens the panel in your browser.
See README.md for what this does, docs/INSTALL.md for setup on your computer,
and docs/CONSOLES.md for pointing a PS3/PS4/PS5 at it.
"""
import sys
import threading
import time
import webbrowser

from emblemtool import config
from emblemtool import consoles
from emblemtool import settings
from emblemtool.proxy import serve as serve_proxy
from emblemtool.web.server import make_server
from emblemtool.web.netinfo import get_lan_ips


def _raise_fd_limit():
    """Ask for more open files than the default, where the OS allows it.

    A console generates a steady stream of short-lived connections and each
    one briefly holds two descriptors. macOS starts a Finder-launched app with
    a soft limit of 256, which a busy session can reach; raising the soft limit
    toward the hard one needs no privileges.
    """
    try:
        import resource
    except ImportError:
        return  # Windows: no such limit to raise
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        target = min(4096, hard) if hard != resource.RLIM_INFINITY else 4096
        if soft < target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
    except (ValueError, OSError):
        pass


def _print_banner(web_port):
    console = consoles.get(settings.get_console())
    addresses = get_lan_ips()

    print("=" * 64)
    print(" BO2 Emblem Toolkit")
    print("=" * 64)
    print(f" Control panel  : http://localhost:{web_port}")
    print(f" Console        : {console.name}")
    if addresses:
        print(f" Proxy setting  : {addresses[0]['ip']} : {config.PROXY_PORT}")
        # More than one candidate is normal (Internet Sharing, VPNs, virtual
        # adapters) and picking the wrong one is the single most common reason
        # a console reports no internet, so show them all rather than guess.
        for entry in addresses[1:]:
            label = f" ({entry['interface']})" if entry["interface"] else ""
            print(f"                  or {entry['ip']}{label}")
    else:
        print(f" Proxy setting  : <this computer's LAN IP> : {config.PROXY_PORT}")
        print("                  (couldn't auto-detect - see docs/INSTALL.md)")
    print(f" Saving data to : {config.ROOT_DIR}")
    print("=" * 64)
    print(" Press Ctrl+C to stop, or use Quit in the control panel.")
    print()


def _start_web_server():
    """The control panel, on the first free port from WEB_PORT upwards.

    Moving it is safe - we open the browser ourselves, and nothing external
    points at it. The proxy port is deliberately not treated this way: the
    console is configured with that number by hand, so it has to stay put and
    fail loudly instead (proxy.startup_error, shown in the panel).
    """
    last_error = None
    for port in range(config.WEB_PORT, config.WEB_PORT + 10):
        try:
            return make_server(port=port), port
        except OSError as e:
            last_error = e
    raise last_error


def main():
    _raise_fd_limit()
    proxy_thread = threading.Thread(target=serve_proxy, daemon=True)
    proxy_thread.start()

    try:
        server, web_port = _start_web_server()
    except OSError as e:
        print(f"Couldn't start the control panel near port {config.WEB_PORT}: {e}")
        print("Set BO2_WEB_PORT to a free port and try again.")
        return 1

    _print_banner(web_port)

    time.sleep(0.3)
    try:
        webbrowser.open(f"http://localhost:{web_port}")
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
