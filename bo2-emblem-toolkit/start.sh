#!/bin/bash
# Linux: run ./start.sh from a terminal.
# On macOS use start.command instead - Finder will open it in Terminal for you.
cd "$(dirname "$0")" || exit 1

PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Python 3.9 or newer is required but wasn't found."
  echo "Install it with your package manager, e.g. sudo apt install python3 python3-pip"
  exit 1
fi

if ! "$PYTHON" -c 'import PIL' >/dev/null 2>&1; then
  echo "Pillow isn't installed. Install it with:"
  echo "  $PYTHON -m pip install -r requirements.txt"
  echo "(or your distro's package, e.g. sudo apt install python3-pil)"
  exit 1
fi

exec "$PYTHON" run.py
