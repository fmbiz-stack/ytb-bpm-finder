"""Paths, ports, and other fixed settings used across the toolkit."""
import os
import sys

APP_NAME = "BO2EmblemToolkit"

IS_FROZEN = bool(getattr(sys, "frozen", False))
IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = os.name == "nt"

# True when running as a macOS .app bundle rather than a bare binary. Anything
# written next to the executable in that case lands *inside* the bundle, where
# it is invisible in Finder and thrown away when the app is replaced - so the
# data directory has to move (see _default_data_dir).
IS_MAC_APP_BUNDLE = IS_FROZEN and ".app/Contents/MacOS/" in os.path.abspath(sys.executable)


def _exe_dir():
    return os.path.dirname(os.path.abspath(sys.executable))


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _user_data_dir():
    """The per-user location this OS expects an app to keep its data in."""
    if IS_MACOS:
        return os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_NAME)


def _default_data_dir():
    """Where captures and the current mode are written.

    From source: the repo root, so everything stays next to the code.

    Frozen: next to the executable, so saved emblems survive between runs
    instead of landing in the temp folder a onefile build unpacks into. The
    exception is a macOS .app bundle, which is a sealed, relocatable directory
    that must be treated as read-only - those get the standard per-user
    Application Support folder instead.

    An existing `saved/` beside the executable always wins, so upgrading an
    installation that already has captures never orphans them.
    """
    if not IS_FROZEN:
        return _repo_root()
    if IS_MAC_APP_BUNDLE:
        beside_bundle = os.path.abspath(os.path.join(_exe_dir(), "..", "..", ".."))
        if os.path.isdir(os.path.join(beside_bundle, "saved")):
            return beside_bundle
        return _user_data_dir()
    return _exe_dir()


# Override for anyone who wants captures somewhere specific (portable installs,
# a shared folder, testing).
ROOT_DIR = os.environ.get("BO2_TOOLKIT_DATA_DIR") or _default_data_dir()

# Where read-only bundled resources (shape reference images, LICENSE) live.
# PyInstaller unpacks these into a temp folder at startup (sys._MEIPASS);
# running from source, they're just files in the repo.
RESOURCE_DIR = getattr(sys, "_MEIPASS", _repo_root())

# Unlike the repo root or an exe's own folder, the per-user data directory
# doesn't exist until something makes it - and on macOS that's the normal
# first-run state. Creating it here means every writer below can assume it.
try:
    os.makedirs(ROOT_DIR, exist_ok=True)
except OSError:
    pass  # surfaced properly when the first write fails

SAVED_DIR = os.path.join(ROOT_DIR, "saved")
SHAPES_DIR = os.path.join(RESOURCE_DIR, "reference_shapes")
STATE_FILE = os.path.join(ROOT_DIR, "state.txt")
SETTINGS_FILE = os.path.join(ROOT_DIR, "settings.json")

ACTIVE_NAME = "_active"  # reserved pseudo-group: the currently armed injection set


def _port(env_name, default):
    try:
        value = int(os.environ.get(env_name, ""))
    except ValueError:
        return default
    return value if 1 <= value <= 65535 else default


PROXY_HOST = "0.0.0.0"
# Overridable because 8080/8090 are popular and something else may already
# hold them - common on a dev machine, and macOS gives no useful error when
# a port is taken by another user's process.
PROXY_PORT = _port("BO2_PROXY_PORT", 8080)
WEB_HOST = "0.0.0.0"
WEB_PORT = _port("BO2_WEB_PORT", 8090)

# How long to wait on the console-facing and upstream sockets. Without these a
# single wedged connection parks a thread forever; consoles drop connections
# without closing them often enough for that to matter.
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 30
