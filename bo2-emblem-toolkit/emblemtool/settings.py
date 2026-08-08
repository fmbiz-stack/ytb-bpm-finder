"""Small persisted settings store.

Separate from state.py: state is the live mode and changes constantly, this is
the handful of choices a user makes once (currently just which console they're
on) and expects to still be there next time they open the tool.
"""
import json
import os
import threading

from . import config
from . import consoles

_lock = threading.Lock()

DEFAULTS = {
    "console": consoles.DEFAULT_CONSOLE,
}


def read_settings():
    try:
        with open(config.SETTINGS_FILE) as f:
            stored = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        stored = {}
    if not isinstance(stored, dict):
        stored = {}
    return {**DEFAULTS, **stored}


def write_settings(values):
    with _lock:
        current = read_settings()
        current.update(values)
        os.makedirs(os.path.dirname(config.SETTINGS_FILE) or ".", exist_ok=True)
        with open(config.SETTINGS_FILE, "w") as f:
            json.dump(current, f, indent=2)
        return current


def get_console():
    """The console key the user picked, validated back to a known preset."""
    return consoles.get(read_settings().get("console")).key


def set_console(key):
    resolved = consoles.get(key).key
    write_settings({"console": resolved})
    return resolved
